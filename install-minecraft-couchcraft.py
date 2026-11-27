#!/usr/bin/env python3
"""Installe ou lance Minecraft 26.3 avec Couchcraft dans Ports sur Batocera."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from tempfile import NamedTemporaryFile, TemporaryDirectory
from urllib.parse import unquote
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

ROOT = Path("/userdata/system/minecraft-couchcraft")
PORTS = Path("/userdata/roms/ports")
PORT_MARKER = "# Minecraft Couchcraft - Batocera"
SCRIPT = "install-minecraft-couchcraft.py"
LEGACY_ROOT = Path("/userdata/system/windows-party/minecraft/couchcraft")
LEGACY_PORT = "PartyDeck - Minecraft 26.3 (Couchcraft).sh"
LEGACY_MARKER = "# PartyDeck Batocera: Minecraft Java"

VERSION = "26.3"
APP = "CLauncher-1.0.3"
INPUT_HELPER = "entrees-manette-v3.py"
JAVA = "25.0.5.1+2"
MOD = "couchcraft.jar"
LEGACY_MOD = "couchcraft-0.2.0.jar"
CURSOR_CLASS = "dev/couchcraft/render/CouchHud.class"
CURSOR_CLASS_SHA256 = "9ac03430d733d4ba79be69d311aa6d125d70de294b2e994f404db0daf5930ee7"
JAVA_RELEASE = re.compile(r"(25\.\d+\.\d+(?:\.\d+)?)\+(\d+)")
MOD_RELEASE = re.compile(r"0\.2\.(\d+)")
UPDATE_INTERVAL = 24 * 60 * 60
INSTANCE = "Couchcraft"
PORT = "Minecraft 26.3 (Couchcraft).sh"
JVM_OPTIONS = "-Dfabric.debug.disableModIds=sodium,iris"

ASSETS = {
  "input": [
    "https://raw.githubusercontent.com/Thomson67/minecraft-couchcraft-batocera/test-manette/entrees-manette-v3.py",
    "sha256",
    "800d0b552f1c7f0e458f86015a486d63cd3e9473117dac131e5452aa30bfad18"
  ],
  "java": [
    "https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.5.1%2B2/OpenJDK25U-jre_x64_linux_hotspot_25.0.5.1_2.tar.gz",
    "sha256",
    "2edef9e4f81ec5ee426d023336d4cfbd7b4644e99884e7a73a6a867b70b17acf"
  ],
  "launcher": [
    "https://github.com/chepupel123/CLauncher/releases/download/v1.0.3/CLauncher-Linux.zip",
    "sha256",
    "75afed952cac87858fd2dc6ec39a662af27c9bdc6f8fbe4ba458b1d42a21dc99"
  ],
  "fabric": [
    "https://maven.fabricmc.net/net/fabricmc/fabric-installer/1.1.2/fabric-installer-1.1.2.jar",
    "sha256",
    "61e035bf7bf70153e127440ce34de47c9036f0a2d0c65d1529454bd35ceefe4f"
  ],
  "couchcraft": [
    "https://github.com/zortos293/Couchcraft/releases/download/v0.2.0/couchcraft-0.2.0.jar",
    "sha256",
    "f9f2b221233397351dd877fbcd9b5084f377cb923826ecd1f66389e02adce7ed"
  ]
}


def write_atomic(destination, content, mode=0o600):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, prefix=".minecraft-", delete=False) as output:
        staged = Path(output.name)
        try:
            output.write(content)
            output.close()
            staged.chmod(mode)
            staged.replace(destination)
        finally:
            staged.unlink(missing_ok=True)


def digest(path, algorithm):
    with path.open("rb") as source:
        result = hashlib.new(algorithm)
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
        return result.hexdigest()


def download(asset, destination):
    url, algorithm, checksum = asset
    if destination.is_file() and digest(destination, algorithm) == checksum:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    name = unquote(url.rsplit("/", 1)[-1])
    print(f"Téléchargement de {name}", flush=True)
    with TemporaryDirectory(dir=destination.parent, prefix=".download-") as directory:
        staged = Path(directory) / "download"
        subprocess.run([
            "curl", "--fail", "--silent", "--show-error", "--location", "--retry", "2",
            "--connect-timeout", "15", "--max-time", "300", "--proto", "=https", "--proto-redir",
            "=https", "--output", str(staged), url,
        ], check=True)
        if digest(staged, algorithm) != checksum:
            raise ValueError(f"Somme {algorithm} incorrecte pour {name}.")
        staged.replace(destination)


def port_is_managed(path):
    if not os.path.lexists(path):
        return True
    if not stat.S_ISREG(path.lstat().st_mode):
        return False
    with path.open() as source:
        return source.readline() == "#!/bin/sh\n" and source.readline().strip() == PORT_MARKER


def graphical_env():
    env = os.environ.copy()
    keys = {"DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR",
            "DBUS_SESSION_BUS_ADDRESS", "PULSE_SERVER", "PIPEWIRE_REMOTE"}
    result = subprocess.run(["pidof", "emulationstation"], capture_output=True, text=True)
    for pid in result.stdout.split():
        try:
            entries = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        except OSError:
            continue
        session = dict(os.fsdecode(item).split("=", 1) for item in entries if b"=" in item)
        if session.get("DISPLAY") or session.get("WAYLAND_DISPLAY"):
            for key in keys:
                if key in session:
                    env[key] = session[key]
                elif key in {"DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY"}:
                    env.pop(key, None)
            break
    env.setdefault("DISPLAY", ":0")
    return env


def screen_status(env):
    display = env["DISPLAY"]
    if not shutil.which("xrandr"):
        return f"DISPLAY={display} (xrandr indisponible)"
    result = subprocess.run(["xrandr", "--current"], env=env, capture_output=True,
                            text=True, timeout=10)
    if result.returncode:
        raise ValueError(f"Affichage X11 inaccessible sur DISPLAY={display}. Lance depuis Ports.")
    current = re.search(r"current (\d+) x (\d+)", result.stdout)
    if not current:
        return f"DISPLAY={display}"
    width, height = map(int, current.groups())
    detail = f"DISPLAY={display} ({width}×{height})"
    if width < 320 or height < 200:
        detail += " — XWayland signale une petite surface avant ouverture de la fenêtre."
    return detail

def install_java25(runtime, asset, version=JAVA):
    destination = runtime / f"temurin-{version}"
    java = destination / "bin/java"
    if java.is_file():
        check_java25(java)
        return java
    runtime.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=runtime, prefix=".java25-") as directory:
        staging = Path(directory)
        archive = staging / "java25.tar.gz"
        download(asset, archive)
        with tarfile.open(archive) as source:
            source.extractall(staging, filter="data")
        extracted = staging / f"jdk-{version}-jre"
        check_java25(extracted / "bin/java")
        extracted.rename(destination)
    return java


def select_java(runtime, java):
    with TemporaryDirectory(dir=runtime, prefix=".java-selection-") as directory:
        staged = Path(directory) / "current"
        staged.symlink_to(java.parent.parent.name, target_is_directory=True)
        staged.replace(runtime / "current")


def game_dir(data):
    return data / "instances" / INSTANCE / ".minecraft"


def enable_fullscreen(game):
    options = game / "options.txt"
    content = options.read_bytes() if options.exists() else b"version:5023\n"
    updated, matches = re.subn(rb"(?m)^fullscreen:[^\r\n]*", b"fullscreen:true", content)
    if not matches:
        newline = b"\r\n" if b"\r\n" in content else b"\n"
        if content and not content.endswith(b"\n"):
            updated += newline
        updated += b"fullscreen:true" + newline
    if not options.exists() or updated != content:
        write_atomic(options, updated)


def mod_version(path):
    with ZipFile(path) as archive:
        info = json.loads(archive.read("fabric.mod.json"))
    requirements = info.get("depends", {})
    version = MOD_RELEASE.fullmatch(info.get("version", ""))
    if (info.get("id") != "couchcraft" or not version
            or requirements != {"java": ">=25", "minecraft": "~26.3", "fabricloader": ">=0.19.5"}):
        raise ValueError(f"Version de Couchcraft incompatible dans {path.name}.")
    return int(version[1])


def install_mod(game):
    mods = game / "mods"
    destination = mods / MOD
    if not destination.is_file():
        download(ASSETS["couchcraft"], destination)
    mod_version(destination)
    old = mods / LEGACY_MOD
    if old.is_file() and digest(old, "sha256") == ASSETS["couchcraft"][2]:
        old.unlink()
    enable_primary_cursor(destination)


def enable_primary_cursor(mod):
    # Only change the unmodified upstream 0.2.0 JAR. Leave future releases
    # and locally modified JARs to their own rendering implementations.
    if digest(mod, "sha256") != ASSETS["couchcraft"][2]:
        return
    output = BytesIO()
    with ZipFile(mod) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        cursor = source.read(CURSOR_CLASS)
        if hashlib.sha256(cursor).hexdigest() != CURSOR_CLASS_SHA256:
            raise ValueError("Classe de rendu Couchcraft 0.2.0 inattendue.")
        # CouchHud.extract: replace !context.primary with context.pad != null.
        # Both conditions use a getfield and a branch to the same destination.
        original = bytes.fromhex("2b b4 00 32 9a 00 3d 2c b4 00 62")
        replacement = bytes.fromhex("2b b4 00 5a c6 00 3d 2c b4 00 62")
        if cursor.count(original) != 1:
            raise ValueError("Condition de rendu du pointeur Couchcraft introuvable.")
        for member in source.infolist():
            content = (cursor.replace(original, replacement) if member.filename == CURSOR_CLASS
                       else source.read(member))
            target.writestr(member, content)
    write_atomic(mod, output.getvalue())


def latest_release(repo):
    response = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--connect-timeout", "4", "--max-time", "8",
         f"https://api.github.com/repos/{repo}/releases/latest"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(response.stdout)


def release_asset(release, repo, filename):
    expected = f"https://github.com/{repo}/releases/download/"
    for asset in release.get("assets", []):
        url, checksum = asset.get("browser_download_url", ""), asset.get("digest") or ""
        if (asset.get("name") == filename and url.startswith(expected)
                and re.fullmatch(r"sha256:[a-f0-9]{64}", checksum)):
            return url, "sha256", checksum.split(":", 1)[1]
    raise ValueError(f"Archive officielle avec SHA-256 introuvable pour {filename}.")


def update_couchcraft(game):
    repo = "zortos293/Couchcraft"
    release = latest_release(repo)
    version = release["tag_name"].removeprefix("v")
    match = MOD_RELEASE.fullmatch(version)
    installed = game / "mods" / MOD
    if not match or int(match[1]) <= mod_version(installed):
        return
    asset = release_asset(release, repo, f"couchcraft-{version}.jar")
    with TemporaryDirectory(dir=installed.parent, prefix=".couchcraft-update-") as directory:
        staged = Path(directory) / MOD
        download(asset, staged)
        if mod_version(staged) != int(match[1]):
            raise ValueError("Version Couchcraft différente de celle annoncée.")
        staged.replace(installed)
    print(f"Couchcraft mis à jour vers {version}.", flush=True)


def update_java(runtime):
    repo = "adoptium/temurin25-binaries"
    release = latest_release(repo)
    version = release["tag_name"].removeprefix("jdk-")
    match = JAVA_RELEASE.fullmatch(version)
    current = JAVA_RELEASE.fullmatch((runtime / "current").resolve().name.removeprefix("temurin-"))
    if not match:
        return
    def parts(value):
        numbers = tuple(map(int, value[1].split(".")))
        return (*numbers, *(0,) * (4 - len(numbers)), int(value[2]))
    if current and parts(match) <= parts(current):
        return
    filename = f"OpenJDK25U-jre_x64_linux_hotspot_{match[1]}_{match[2]}.tar.gz"
    java = install_java25(runtime, release_asset(release, repo, filename), version)
    select_java(runtime, java)
    print(f"Temurin mis à jour vers {version}.", flush=True)


def check_updates(root, runtime, force=False):
    stamp = root / ".update-check"
    if not force and stamp.is_file() and time.time() - stamp.stat().st_mtime < UPDATE_INTERVAL:
        return
    stamp.touch()
    print("Recherche de mises à jour compatibles…", flush=True)
    succeeded = True
    for update, target in ((update_couchcraft, game_dir(data_dir(root))), (update_java, runtime)):
        try:
            update(target)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError, BadZipFile) as error:
            print(f"Mise à jour reportée : {error}", file=sys.stderr)
            succeeded = False
    return succeeded


def check_java25(executable):
    result = subprocess.run([executable, "-version"], capture_output=True, text=True,
                            timeout=15, check=True)
    version = re.search(r'version "(25(?:[.+-][^"]*)?)"', result.stderr + result.stdout)
    if not version:
        raise ValueError(f"Java 25 attendu dans {executable}.")
    return version.group(1)


def install_clauncher(root, asset):
    destination = root / APP
    if (destination / "AppRun").is_file():
        return
    with TemporaryDirectory(dir=root, prefix=".clauncher-") as directory:
        staging = Path(directory)
        archive = staging / "clauncher.zip"
        download(asset, archive)
        image = staging / "CLauncher.AppImage"
        # Upstream's release ZIP contains a second ZIP with the AppImage.
        with ZipFile(archive) as outer, ZipFile(BytesIO(outer.read("CLauncher-Linux.zip"))) as inner:
            image.write_bytes(inner.read("CLauncher-Linux/CLauncher-x86_64.AppImage"))
        image.chmod(0o755)
        subprocess.run([image, "--appimage-extract"], cwd=staging, check=True,
                       stdout=subprocess.DEVNULL, timeout=60)
        extracted = staging / "squashfs-root"
        if not os.access(extracted / "AppRun", os.X_OK):
            raise ValueError("Exécutable absent de l’AppImage CLauncher.")
        extracted.rename(destination)


def data_dir(root):
    return root / "home/.clauncher"


def seed_instance(data, java):
    instance = data / "instances" / INSTANCE
    manifest = instance / "instance.json"
    profile = json.loads(manifest.read_text()) if manifest.exists() else {
        "name": INSTANCE, "mc_version": VERSION, "version_id": VERSION,
        "mod_loader": "fabric", "memory_mb": 4096, "nickname": "Joueur1",
    }
    profile["java_path"] = str(java)
    write_atomic(manifest, (json.dumps(profile, indent=2) + "\n").encode())
    settings = data / "launcher_settings.json"
    if not settings.exists():
        defaults = {"nickname": profile["nickname"], "selected_version": VERSION,
                    "mod_loader": 1, "lang": "en", "memory_index": 4}
        write_atomic(settings, (json.dumps(defaults, indent=2) + "\n").encode())

    # CLauncher uses its managed runtime path for installing Fabric even when its
    # game instance already specifies a custom Java executable.
    java_link = data / "runtime/java25"
    java_link.parent.mkdir(parents=True, exist_ok=True)
    if not os.path.lexists(java_link):
        java_link.symlink_to(java.parent.parent, target_is_directory=True)
    elif java_link.is_symlink() and java_link.resolve() != java.parent.parent.resolve():
        raise ValueError(f"Lien Java inattendu dans {java_link}.")
    elif not java_link.is_symlink():
        check_java25(java_link / "bin/java")

    return instance / ".minecraft"


@contextmanager
def session_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / "minecraft.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Une session Minecraft est déjà en cours. Ferme le lanceur avant de réessayer.") from error
        yield lock


def migrate_legacy_data(data):
    source = data_dir(LEGACY_ROOT)
    relative = Path("instances") / INSTANCE
    if data.exists() or not (source / relative / "instance.json").is_file():
        return

    print("Copie de l’ancien profil Couchcraft et des mondes…", flush=True)
    data.parent.mkdir(parents=True, exist_ok=True)
    with session_lock(LEGACY_ROOT), TemporaryDirectory(dir=data.parent, prefix=".migration-") as directory:
        staged = Path(directory) / ".clauncher"
        shutil.copytree(source / relative, staged / relative,
                        ignore=shutil.ignore_patterns("logs", "crash-reports"))
        if (source / "shared").is_dir():
            shutil.copytree(source / "shared", staged / "shared")
        settings = source / "launcher_settings.json"
        if settings.is_file():
            shutil.copy2(settings, staged / settings.name)
        staged.rename(data)


def port_content(script, marker):
    command = shlex.join(["python3", str(script), "jouer"])
    return f"#!/bin/sh\n{marker}\nexec {command}\n".encode()


def retire_legacy_port(ports):
    entry = ports / LEGACY_PORT
    backup = entry.with_suffix(".sh.disabled")
    if not entry.is_file() or entry.is_symlink() or os.path.lexists(backup):
        return
    if entry.read_bytes() == port_content(LEGACY_ROOT / "partydeck_couchcraft.py", LEGACY_MARKER):
        entry.rename(backup)
        print(f"Ancienne entrée Couchcraft désactivée : {backup.name}")


def install(root, ports, runtime):
    port = ports / PORT
    if not port_is_managed(port):
        raise ValueError(f"Une entrée existe déjà dans {port}.")
    java = runtime / "current/bin/java"
    if not java.is_file():
        select_java(runtime, install_java25(runtime, ASSETS["java"]))
    check_java25(java)
    install_clauncher(root, ASSETS["launcher"])
    download(ASSETS["input"], root / INPUT_HELPER)
    data = data_dir(root)
    migrate_legacy_data(data)
    game = seed_instance(data, java)
    download(ASSETS["fabric"], data / "cache/fabric-installer.jar")
    install_mod(game)
    enable_fullscreen(game)
    write_atomic(root / SCRIPT, Path(__file__).read_bytes(), 0o755)
    write_atomic(port, port_content(root / SCRIPT, PORT_MARKER), 0o755)
    retire_legacy_port(ports)
    print(f"Couchcraft installé. Actualise les listes dans EmulationStation.\n{port}")


def launcher_env(root):
    env = graphical_env()
    if "XAUTHORITY" not in env:
        authority = Path.home() / ".Xauthority"
        if authority.is_file():
            env["XAUTHORITY"] = str(authority)
    env.update(HOME=str(root / "home"), APPDIR=str(root / APP))
    if env.get("WAYLAND_DISPLAY"):
        # Keep both windows observable by the keyboard helper on XWayland.
        env.setdefault("SDL_VIDEO_DRIVER", "x11")
    # The upstream launcher ticks its performance mods option on every startup.
    # Fabric skips these conflicting mod IDs even if the launcher downloads them.
    previous = env.get("JAVA_TOOL_OPTIONS", "").strip()
    env["JAVA_TOOL_OPTIONS"] = f"{previous} {JVM_OPTIONS}".lstrip()
    return env


def start_input_helper(root, env, mode, log_name):
    try:
        with (root / log_name).open("wb") as output:
            subprocess.Popen(
                [sys.executable, root / INPUT_HELPER, mode, str(os.getpid())],
                env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            )
    except OSError as error:
        print(f"Entrée manette ({mode}) indisponible : {error}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="installer",
                        choices=("installer", "jouer", "verifier", "mettre-a-jour"))
    args = parser.parse_args()
    if platform.machine() != "x86_64" or not shutil.which("batocera-version"):
        parser.exit(1, "Minecraft Couchcraft est prévu pour Batocera x86_64.\n")

    root = ROOT
    runtime = root / "runtime/java"
    try:
        with session_lock(root) as lock:
            if args.action == "installer":
                install(root, PORTS, runtime)
                return 0
            app = root / APP / "AppRun"
            java = runtime / "current/bin/java"
            version = check_java25(java)
            if args.action == "mettre-a-jour":
                return 0 if check_updates(root, runtime, force=True) else 1
            env = launcher_env(root)
            print(f"Java {version} · {java}\n{screen_status(env)}", flush=True)
            if not app.is_file():
                raise ValueError("CLauncher est introuvable. Relance l’installateur.")
            if args.action == "verifier":
                print(f"CLauncher · {app}\nDonnées · {data_dir(root)}")
                print(f"Journal de la manette CLauncher · {root / 'manette-clauncher.log'}")
                print(f"Journal du clavier virtuel · {root / 'clavier-virtuel.log'}")
                return 0
            check_updates(root, runtime)
            # Hold the lock until CLauncher exits, including its game session.
            os.set_inheritable(lock.fileno(), True)
            os.chdir(root)
            start_input_helper(root, env, "souris", "manette-clauncher.log")
            start_input_helper(root, env, "clavier", "clavier-virtuel.log")
            os.execve(app, [app], env)
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError, BadZipFile) as error:
        parser.exit(1, f"Minecraft Couchcraft : {error}\n")


if __name__ == "__main__":
    sys.exit(main())
