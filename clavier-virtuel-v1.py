#!/usr/bin/env python3
"""Clavier du port Minecraft, adapté du clavier d’Ultimate Wine Toolbox par Thomson.

Utilise la configuration des manettes d’EmulationStation. La fenêtre GTK
garde le focus sur CLauncher ou Minecraft et les touches sont émises via uinput.
"""
import ctypes as C
import ctypes.util
import os
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET


class KeyboardModel:
    def __init__(self, french=True):
        self.french, self.upper, self.symbols = french, False, False
        self.row = self.col = 0

    def rows(self):
        if self.symbols:
            rows = [list('1234567890'), list('-_@./:!?+='), list('()[]#%,;\'"')]
        elif self.french:
            rows = [list('azertyuiop'), list('qsdfghjklm'), list('wxcvbn')+list('éèàç')]
        else:
            rows = [list('qwertyuiop'), list('asdfghjkl'), list('zxcvbnm')]
        if self.upper and not self.symbols:
            rows = [[char.upper() for char in row] for row in rows]
        return rows+[['cursor_left', 'cursor_down', 'cursor_up', 'cursor_right', 'home', 'end', 'delete'],
                     ['shift', 'symbols', 'backspace', 'space', 'enter', 'close']]

    def selected(self):
        rows = self.rows()
        self.row %= len(rows)
        self.col = min(self.col, len(rows[self.row])-1)
        return rows[self.row][self.col]

    def move(self, direction):
        if direction in ('up', 'down'):
            self.row = (self.row+(1 if direction == 'down' else -1)) % len(self.rows())
            self.col = min(self.col, len(self.rows()[self.row])-1)
        else:
            self.col = (self.col+(1 if direction == 'right' else -1)) % len(self.rows()[self.row])

    def activate(self, action=None):
        action = action or self.selected()
        if action == 'shift': self.upper = not self.upper
        elif action == 'symbols': self.symbols = not self.symbols
        else: return action
        self.selected()
        return None


class KeySender:
    """Resolve characters against the desktop XKB map, then send Linux keys.

    The overlay never takes keyboard focus. Its uinput keyboard sends to the
    already-focused game, so there is no Alt+Tab or clipboard dependency.
    """
    def __init__(self):
        import evdev
        self.e = evdev.ecodes
        self.x = C.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
        self.x.XOpenDisplay.argtypes = [C.c_char_p]; self.x.XOpenDisplay.restype = C.c_void_p
        self.x.XkbKeycodeToKeysym.argtypes = [C.c_void_p, C.c_ubyte, C.c_int, C.c_int]
        self.x.XkbKeycodeToKeysym.restype = C.c_ulong
        self.x.XCloseDisplay.argtypes = [C.c_void_p]
        self.display = self.x.XOpenDisplay(os.environ.get('DISPLAY', ':0').encode())
        if not self.display: raise RuntimeError('Desktop XKB map unavailable')
        self.characters = {}
        for level, mods in [(0, ()), (1, (42,)), (2, (100,)), (3, (42, 100))]:
            for code in range(8, 256):
                symbol = self.x.XkbKeycodeToKeysym(self.display, code, 0, level)
                if 0x20 <= symbol <= 0xff:
                    self.characters.setdefault(chr(symbol), (code-8, mods))
                elif symbol & 0xff000000 == 0x01000000:
                    self.characters.setdefault(chr(symbol & 0xffffff), (code-8, mods))
        try:
            self.ui = evdev.UInput({self.e.EV_KEY: list(range(1, 256))}, name='Couchcraft Virtual Keyboard')
        except BaseException:
            self.x.XCloseDisplay(self.display)
            raise

    def send(self, action):
        special = {'backspace': 14, 'space': 57, 'enter': 28, 'delete': 111,
                   'cursor_left': 105, 'cursor_right': 106, 'cursor_up': 103,
                   'cursor_down': 108, 'home': 102, 'end': 107}
        if action in special: key, mods = special[action], ()
        elif action in self.characters: key, mods = self.characters[action]
        else: raise ValueError('Character unavailable in the current desktop keyboard layout')
        pressed = []
        try:
            for code in (*mods, key):
                self.ui.write(self.e.EV_KEY, code, 1); self.ui.syn(); pressed.append(code)
            # Allow the game to observe a complete key press.
            time.sleep(.025)
        finally:
            for code in reversed(pressed): self.ui.write(self.e.EV_KEY, code, 0)
            self.ui.syn()

    def close(self):
        self.ui.close()
        self.x.XCloseDisplay(self.display)


def gtk_dependencies():
    display_environment()
    os.environ.setdefault('NO_AT_BRIDGE', '1')
    os.environ['GDK_BACKEND'] = 'wayland' if os.environ.get('WAYLAND_DISPLAY') else 'x11'
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
    from gi.repository import Gtk, Gdk, GLib
    if not Gtk.init_check()[0]: raise RuntimeError('GTK display unavailable')
    layer = None
    if os.environ.get('WAYLAND_DISPLAY'):
        gi.require_version('GtkLayerShell', '0.1')
        from gi.repository import GtkLayerShell
        if not GtkLayerShell.is_supported(): raise RuntimeError('Non-focus-stealing Wayland layer unavailable')
        layer = GtkLayerShell
    return Gtk, Gdk, GLib, layer


def display_environment():
    os.environ.setdefault('DISPLAY', ':0')
    if 'XAUTHORITY' not in os.environ and Path('/var/lib/.Xauthority').is_file():
        os.environ['XAUTHORITY'] = '/var/lib/.Xauthority'


class Overlay:
    def __init__(self, dependencies, action, french=True):
        self.Gtk, self.Gdk, self.GLib, layer = dependencies
        Gtk, Gdk = self.Gtk, self.Gdk
        self.model, self.action = KeyboardModel(french), action
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL if layer else Gtk.WindowType.POPUP)
        self.window.set_title('Clavier virtuel Minecraft')
        self.window.set_decorated(False)
        self.window.set_accept_focus(False); self.window.set_focus_on_map(False)
        self.window.set_skip_taskbar_hint(True); self.window.set_skip_pager_hint(True)
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        if layer:
            layer.init_for_window(self.window)
            layer.set_namespace(self.window, 'couchcraft-virtual-keyboard')
            layer.set_layer(self.window, layer.Layer.OVERLAY)
            layer.set_keyboard_mode(self.window, layer.KeyboardMode.NONE)
            layer.set_exclusive_zone(self.window, 0)
            layer.set_anchor(self.window, layer.Edge.BOTTOM, True)
            layer.set_margin(self.window, layer.Edge.BOTTOM, 16)
            if monitor: layer.set_monitor(self.window, monitor)
        else:
            self.window.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
            self.window.set_keep_above(True)
        bounds = monitor.get_geometry() if monitor else None
        width = min(1040, max(420, bounds.width-40)) if bounds else 960
        height = min(440, max(280, int(bounds.height*.42))) if bounds else 400
        self.window.set_size_request(width, height)
        if not layer and bounds:
            self.window.move(bounds.x+(bounds.width-width)//2, bounds.y+bounds.height-height-16)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for side in ('top', 'bottom', 'start', 'end'): getattr(box, 'set_margin_'+side)(12)
        self.window.add(box)
        title = ('Clavier — Hotkey + Select (ou R1) : afficher / masquer' if french else
                 'Keyboard — Hotkey + Select (or R1): show / hide')
        box.pack_start(Gtk.Label(label=title), False, False, 0)
        self.grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.pack_start(self.grid, True, True, 0)
        legend = ('Croix/bas : saisir · Rond/droite : fermer · Carré/gauche : effacer · Triangle/haut : espace\nL1 : majuscules · R1 : chiffres · Start : Entrée' if french else
                  'South: type · East: close · West: backspace · North: space\nL1: shift · R1: numbers · Start: Enter')
        self.message = Gtk.Label(label=legend); self.message.set_line_wrap(True)
        box.pack_start(self.message, False, False, 0)
        css = Gtk.CssProvider()
        css.load_from_data(b'window { background-color: #182230; } label { color: #edf4ff; font-size: 14pt; } button { background-image: none; background-color: #304158; color: white; border: 1px solid #59708e; border-radius: 8px; font-size: 19pt; } button.selected { background-color: #148082; border: 3px solid #a7f4e7; }')
        Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.labels = {'shift': '⇧', 'symbols': 'ABC / 123', 'backspace': '⌫',
                       'cursor_left': '←', 'cursor_right': '→', 'cursor_up': '↑', 'cursor_down': '↓',
                       'home': 'Début' if french else 'Home', 'end': 'Fin' if french else 'End',
                       'delete': 'Suppr' if french else 'Delete',
                       'space': 'Espace' if french else 'Space', 'enter': 'Entrée' if french else 'Enter',
                       'close': 'Fermer' if french else 'Close'}
        self.render()

    def render(self):
        for child in self.grid.get_children(): self.grid.remove(child)
        for row, keys in enumerate(self.model.rows()):
            line = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=6)
            line.set_homogeneous(True)
            self.grid.pack_start(line, True, True, 0)
            for col, key in enumerate(keys):
                button = self.Gtk.Button(label=self.labels.get(key, key))
                button.set_can_focus(False)
                button.connect('clicked', lambda _, action=key: self.action(action))
                if (row, col) == (self.model.row, self.model.col):
                    button.get_style_context().add_class('selected')
                line.pack_start(button, True, True, 0)
        self.grid.show_all()

    def visible(self): return self.window.get_visible()
    def show(self): self.window.show_all()
    def hide(self): self.window.hide()
    def close(self): self.window.destroy()


def guid_identity(value):
    try:
        raw = bytes.fromhex(value)
    except (TypeError, ValueError):
        return None
    if len(raw) == 16:
        return tuple(int.from_bytes(raw[i:i+2], "little") for i in (0, 4, 8, 12))
    return None


def mappings(config, keys, axes):
    result = {}
    hats = [code for code in range(16, 24, 2) if code in axes and code+1 in axes]
    for item in config.findall("input"):
        name, kind = item.get("name", ""), item.get("type")
        try:
            code = int(item.get("code", "-1"))
            value = int(item.get("value", "1"))
            if kind == "hat":
                if not 16 <= code <= 23:
                    code = hats[int(item.get("id", code))]
                base = code & ~1
                code, value = {1: (base+1, -1), 2: (base, 1),
                               4: (base+1, 1), 8: (base, -1)}[value]
                kind = "axis"
        except (ValueError, TypeError, IndexError, KeyError):
            continue
        if (kind == "button" and code in keys) or (kind == "axis" and code in axes):
            result[name] = (kind, code, 1 if value >= 0 else -1)
    for first, second in (("left", "right"), ("up", "down")):
        match = result.get("joystick1"+first)
        if match:
            kind, code, sign = match
            result["stick"+first] = match
            result["stick"+second] = (kind, code, -sign)
    return result


class Controller:
    def __init__(self, device, mapping, ecodes):
        self.device, self.mapping, self.e = device, mapping, ecodes
        buttons = [mapping.get(name) for name in ("hotkey", "select", "pagedown")]
        hotkey, select, shoulder = buttons
        self.shortcut = next((name for name, button in (("select", select), ("pagedown", shoulder))
                              if hotkey and button and hotkey[0] == button[0] == "button"
                              and hotkey[1] != button[1]), None)
        self.limits = {code: device.absinfo(code) for kind, code, _ in mapping.values()
                       if kind == "axis"}
        if not self.shortcut or not {"a", "b"} <= self.mapping.keys():
            raise ValueError("Raccourci Hotkey et boutons de navigation non configurés")
        self.values = {code: limits.value for code, limits in self.limits.items()}
        self.buttons = set(device.active_keys())
        self.held = self.logical()
        self.captured = False
        self.repeat = None
        self.repeat_at = 0.0

    def logical(self):
        held = set()
        for name, (kind, code, sign) in self.mapping.items():
            if kind == "button":
                pressed = code in self.buttons
            else:
                limits = self.limits[code]
                center = (limits.min + limits.max) / 2
                pressed = sign * (self.values[code] - center) > .55 * (limits.max - center)
            if pressed:
                held.add(name.removeprefix("stick"))
        return held

    def poll(self, now):
        events = []
        for _ in range(32):
            try:
                events.extend(self.device.read())
            except BlockingIOError:
                break
        if any(event.type == self.e.EV_SYN and event.code == self.e.SYN_DROPPED
               for event in events):
            self.buttons = set(self.device.active_keys())
            self.values = {code: self.device.absinfo(code).value for code in self.limits}
            self.held = self.logical()
            self.repeat = None
            return []
        actions = []
        chord = {"hotkey", self.shortcut}
        for event in events:
            if event.type == self.e.EV_KEY:
                if event.value:
                    self.buttons.add(event.code)
                else:
                    self.buttons.discard(event.code)
            elif event.type == self.e.EV_ABS and event.code in self.limits:
                self.values[event.code] = event.value
            else:
                continue
            held = self.logical()
            if chord <= held and not chord <= self.held:
                actions.append("toggle")
            if self.captured and "hotkey" not in held:
                actions.extend(name for name in ("up", "down", "left", "right", "a", "b",
                                                 "x", "y", "start", "pageup", "pagedown")
                               if name in held - self.held)
            self.held = held
        direction = next((name for name in ("up", "down", "left", "right")
                          if name in self.held), None)
        if direction != self.repeat:
            self.repeat, self.repeat_at = direction, now + .38
        elif direction and self.captured and "hotkey" not in self.held and now >= self.repeat_at:
            actions.append(direction)
            self.repeat_at = now + .10
        return actions

    def grab(self):
        self.device.grab()
        self.captured = True

    def ungrab(self):
        if self.captured:
            self.captured = False
            self.device.ungrab()
        self.repeat = None


def discover(known, evdev):
    paths = ("/userdata/system/configs/emulationstation/es_input.cfg",
             "/usr/share/emulationstation/es_input.cfg")
    configs = []
    for path in paths:
        if Path(path).is_file():
            configs.extend(item for item in ET.parse(path).getroot().findall("inputConfig")
                           if item.get("type") == "joystick")
    for path in set(evdev.list_devices()) - known.keys():
        device = None
        try:
            device = evdev.InputDevice(path)
            identity = tuple(getattr(device.info, name)
                             for name in ("bustype", "vendor", "product", "version"))
            caps = device.capabilities(absinfo=False)
            keys = caps.get(evdev.ecodes.EV_KEY, [])
            axes = caps.get(evdev.ecodes.EV_ABS, [])
            if not any(0x120 <= key < 0x140 for key in keys):
                continue
            for item in configs:
                if item.get("deviceName") != device.name and guid_identity(item.get("deviceGUID")) != identity:
                    continue
                try:
                    known[path] = Controller(device, mappings(item, keys, axes), evdev.ecodes)
                    print(f"Manette détectée · {device.name} · Hotkey + "
                          f"{'Select' if known[path].shortcut == 'select' else 'R1'}", flush=True)
                    break
                except (OSError, ValueError):
                    continue
        except OSError:
            pass
        finally:
            if device is not None and path not in known:
                device.close()


class Focus:
    """Locate the X11/XWayland input window and verify its process ancestry."""
    def __init__(self, sender, launcher):
        self.x, self.display = sender.x, sender.display
        self.launcher = launcher
        x = self.x
        x.XGetInputFocus.argtypes = [C.c_void_p, C.POINTER(C.c_ulong), C.POINTER(C.c_int)]
        x.XInternAtom.argtypes = [C.c_void_p, C.c_char_p, C.c_int]
        x.XInternAtom.restype = C.c_ulong
        x.XGetWindowProperty.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong,
            C.c_long, C.c_long, C.c_int, C.c_ulong, C.POINTER(C.c_ulong),
            C.POINTER(C.c_int), C.POINTER(C.c_ulong), C.POINTER(C.c_ulong),
            C.POINTER(C.c_void_p)]
        x.XQueryTree.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
            C.POINTER(C.c_ulong), C.POINTER(C.c_void_p), C.POINTER(C.c_uint)]
        x.XFree.argtypes = [C.c_void_p]
        self.error = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)(lambda *_: 0)
        x.XSetErrorHandler.argtypes = [C.c_void_p]
        x.XSetErrorHandler(self.error)
        self.atom = x.XInternAtom(self.display, b"_NET_WM_PID", 0)

    def window_pid(self, window):
        actual, count, remaining = C.c_ulong(), C.c_ulong(), C.c_ulong()
        fmt, data = C.c_int(), C.c_void_p()
        try:
            status = self.x.XGetWindowProperty(self.display, window, self.atom,
                0, 1, 0, 6, C.byref(actual), C.byref(fmt),
                C.byref(count), C.byref(remaining), C.byref(data))
            if status == 0 and count.value == 1 and fmt.value == 32 and data:
                return C.cast(data, C.POINTER(C.c_ulong))[0]
            return 0
        finally:
            if data:
                self.x.XFree(data)

    def owned(self):
        window, revert = C.c_ulong(), C.c_int()
        self.x.XGetInputFocus(self.display, C.byref(window), C.byref(revert))
        for _ in range(12):
            if window.value <= 1:
                return False
            pid = self.window_pid(window.value)
            if pid:
                return self.has_launcher_ancestor(pid)
            root, parent, children, count = C.c_ulong(), C.c_ulong(), C.c_void_p(), C.c_uint()
            status = self.x.XQueryTree(self.display, window, C.byref(root),
                                      C.byref(parent), C.byref(children), C.byref(count))
            if children:
                self.x.XFree(children)
            if not status or parent.value == window.value:
                return False
            window = parent
        return False

    def has_launcher_ancestor(self, pid):
        for _ in range(12):
            if pid == self.launcher:
                return True
            if pid <= 1:
                return False
            try:
                stat = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
                pid = int(stat[1])
            except (OSError, ValueError, IndexError):
                return False
        return False


def run(launcher):
    import evdev

    deps = gtk_dependencies()
    Gtk, _, GLib, _ = deps
    sender = KeySender()
    devices = {}
    active = pending = None
    quiet = None
    refresh_at = 0.0

    def hide():
        nonlocal active, pending, quiet
        overlay.hide()
        if active:
            try:
                active.ungrab()
            except OSError:
                pass
        active = pending = quiet = None

    def action(key):
        nonlocal pending, quiet
        if not active or not focus.owned():
            hide()
        elif key == "close":
            pending, quiet = active, None
        elif key in ("shift", "symbols"):
            overlay.model.activate(key)
            overlay.render()
        else:
            try:
                sender.send(key)
            except ValueError as error:
                overlay.message.set_text(str(error))
            if key == "enter":
                pending, quiet = active, None

    def tick():
        nonlocal active, pending, quiet, refresh_at
        if os.getppid() != launcher:
            Gtk.main_quit()
            return False
        now = time.monotonic()
        if now >= refresh_at:
            discover(devices, evdev)
            refresh_at = now + 2.0
        if (active or pending) and not focus.owned():
            hide()
        for path, controller in list(devices.items()):
            try:
                actions = controller.poll(now)
            except OSError:
                if controller in (active, pending):
                    hide()
                controller.device.close()
                devices.pop(path)
                continue
            for key in actions:
                if key == "toggle" and not pending and focus.owned():
                    if not active or active is controller:
                        pending, quiet = controller, None
                elif active is controller and not pending:
                    if key in ("up", "down", "left", "right"):
                        overlay.model.move(key)
                        overlay.render()
                    else:
                        action({"b": overlay.model.selected(), "a": "close", "x": "space",
                                "y": "backspace", "start": "enter",
                                "pageup": "shift", "pagedown": "symbols"}[key])
        if pending:
            if pending.buttons or pending.held:
                quiet = None
            elif quiet is None:
                quiet = now
            elif now - quiet >= .12:
                if active:
                    hide()
                else:
                    try:
                        pending.grab()
                        active = pending
                        overlay.show()
                    except OSError as error:
                        print(f"Clavier virtuel · capture impossible · {error}", flush=True)
                    pending = quiet = None
        return True

    def on_tick():
        try:
            return tick()
        except (OSError, ValueError, RuntimeError, ET.ParseError) as error:
            print(f"Clavier virtuel · {error}", flush=True)
            Gtk.main_quit()
            return False

    try:
        focus = Focus(sender, launcher)
        overlay = Overlay(deps, action)
        print("Clavier virtuel Minecraft prêt", flush=True)
        GLib.timeout_add(25, on_tick)
        Gtk.main()
    finally:
        for controller in devices.values():
            controller.device.close()
        sender.close()


if __name__ == "__main__":
    try:
        run(int(sys.argv[1]))
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        print(f"Clavier virtuel indisponible · {error}", file=sys.stderr)
        sys.exit(1)
