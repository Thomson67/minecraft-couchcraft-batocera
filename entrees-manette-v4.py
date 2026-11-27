#!/usr/bin/env python3
"""Souris de CLauncher et clavier virtuel, adaptés d’Ultimate Wine Toolbox par Thomson.

Utilise la configuration des manettes d’EmulationStation. La fenêtre GTK
garde le focus sur CLauncher ou Minecraft. Les entrées sont émises via uinput.
"""
import ctypes as C
import math
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
    def __init__(self, focus):
        import evdev
        self.e = evdev.ecodes
        x = focus.x
        x.XkbKeycodeToKeysym.argtypes = [C.c_void_p, C.c_ubyte, C.c_int, C.c_int]
        x.XkbKeycodeToKeysym.restype = C.c_ulong
        self.characters = {}
        for level, mods in [(0, ()), (1, (42,)), (2, (100,)), (3, (42, 100))]:
            for code in range(8, 256):
                symbol = x.XkbKeycodeToKeysym(focus.display, code, 0, level)
                if 0x20 <= symbol <= 0xff:
                    self.characters.setdefault(chr(symbol), (code-8, mods))
                elif symbol & 0xff000000 == 0x01000000:
                    self.characters.setdefault(chr(symbol & 0xffffff), (code-8, mods))
        self.ui = evdev.UInput({self.e.EV_KEY: list(range(1, 256))}, name='Couchcraft Virtual Keyboard')

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
    def __init__(self, device, mapping, ecodes, mouse=False):
        self.device, self.mapping, self.e = device, mapping, ecodes
        self.mouse = mouse
        buttons = [mapping.get(name) for name in ("hotkey", "select", "pagedown")]
        hotkey, select, shoulder = buttons
        self.shortcut = next((name for name, button in (("select", select), ("pagedown", shoulder))
                              if hotkey and button and hotkey[0] == button[0] == "button"
                              and hotkey[1] != button[1]), None)
        self.limits = {code: device.absinfo(code) for kind, code, _ in mapping.values()
                       if kind == "axis"}
        if not mouse and (not self.shortcut or not {"a", "b"} <= self.mapping.keys()):
            raise ValueError("Raccourci Hotkey et boutons de navigation non configurés")
        self.values = {code: limits.value for code, limits in self.limits.items()}
        self.buttons = set(device.active_keys())
        self.held = self.logical()
        self.captured = False
        self.repeat = None
        self.repeat_at = 0.0

    def strength(self, name):
        kind, code, sign = self.mapping.get(name, ("button", -1, 1))
        if kind == "button":
            return float(code in self.buttons)
        limits = self.limits[code]
        center = (limits.min + limits.max) / 2
        return sign * (self.values[code] - center) / max(1, limits.max - center)

    def logical(self):
        return {name.removeprefix("stick") for name in self.mapping if self.strength(name) > .55}

    def pointer_velocity(self):
        dx, dy = (self.strength("stickright"), self.strength("stickdown"))
        length = math.hypot(dx, dy)
        deadzone = .14
        if length > deadzone:
            tilt = (min(length, 1) - deadzone) / (1 - deadzone)
            speed = 820 * tilt ** 1.85 / length
            return dx * speed, dy * speed
        left, right, up, down = (max(0.0, self.strength(direction))
                                 for direction in ("left", "right", "up", "down"))
        return (
            230 * (right - left),
            230 * (down - up),
        )

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
            if self.mouse and ("b" in held) != ("b" in self.held):
                if "b" not in held or "hotkey" not in held:
                    actions.append("press" if "b" in held else "release")
            if self.mouse and "start" in held - self.held and "hotkey" not in held:
                actions.append("play")
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


def standard_pointer_mapping(keys, axes, e):
    result = {}
    if e.BTN_SOUTH in keys:
        result["b"] = ("button", e.BTN_SOUTH, 1)
    if e.BTN_START in keys:
        result["start"] = ("button", e.BTN_START, 1)
    for first, second, axis, hat, button1, button2 in (
        ("left", "right", e.ABS_X, e.ABS_HAT0X, e.BTN_DPAD_LEFT, e.BTN_DPAD_RIGHT),
        ("up", "down", e.ABS_Y, e.ABS_HAT0Y, e.BTN_DPAD_UP, e.BTN_DPAD_DOWN),
    ):
        if axis in axes:
            result["stick"+first] = ("axis", axis, -1)
            result["stick"+second] = ("axis", axis, 1)
        for direction, button, sign in ((first, button1, -1), (second, button2, 1)):
            if button in keys:
                result[direction] = ("button", button, 1)
            elif hat in axes:
                result[direction] = ("axis", hat, sign)
    return result


def discover(known, evdev, mouse=False, device_paths=None):
    if device_paths is None:
        device_paths = set(evdev.list_devices())
    candidates = device_paths - known.keys()
    if not candidates:
        return
    paths = ("/userdata/system/configs/emulationstation/es_input.cfg",
             "/usr/share/emulationstation/es_input.cfg")
    configs = []
    for path in paths:
        if Path(path).is_file():
            configs.extend(item for item in ET.parse(path).getroot().findall("inputConfig")
                           if item.get("type") == "joystick")
    for path in candidates:
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
                    mapped = mappings(item, keys, axes)
                    if mouse:
                        mapped = standard_pointer_mapping(keys, axes, evdev.ecodes) | mapped
                        if "b" not in mapped:
                            continue
                    known[path] = Controller(device, mapped, evdev.ecodes, mouse)
                    break
                except (OSError, ValueError):
                    continue
            if mouse and path not in known:
                mapped = standard_pointer_mapping(keys, axes, evdev.ecodes)
                if "b" in mapped:
                    known[path] = Controller(device, mapped, evdev.ecodes, mouse=True)
            if path in known:
                mode = ("Pointeur CLauncher" if mouse else
                        f"Hotkey + {'Select' if known[path].shortcut == 'select' else 'R1'}")
                print(f"Manette détectée · {device.name} · {mode}", flush=True)
        except OSError:
            pass
        finally:
            if device is not None and path not in known:
                device.close()


class Focus:
    """Locate the X11/XWayland input window and verify its process ancestry."""
    def __init__(self, launcher):
        self.launcher = launcher
        self.x = x = C.CDLL("libX11.so.6")
        x.XOpenDisplay.argtypes = [C.c_char_p]
        x.XOpenDisplay.restype = C.c_void_p
        x.XCloseDisplay.argtypes = [C.c_void_p]
        x.XGetInputFocus.argtypes = [C.c_void_p, C.POINTER(C.c_ulong), C.POINTER(C.c_int)]
        x.XInternAtom.argtypes = [C.c_void_p, C.c_char_p, C.c_int]
        x.XInternAtom.restype = C.c_ulong
        x.XGetWindowProperty.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong,
            C.c_long, C.c_long, C.c_int, C.c_ulong, C.POINTER(C.c_ulong),
            C.POINTER(C.c_int), C.POINTER(C.c_ulong), C.POINTER(C.c_ulong),
            C.POINTER(C.c_void_p)]
        x.XQueryTree.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
            C.POINTER(C.c_ulong), C.POINTER(C.c_void_p), C.POINTER(C.c_uint)]
        x.XGetGeometry.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
            C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_uint),
            C.POINTER(C.c_uint), C.POINTER(C.c_uint), C.POINTER(C.c_uint)]
        x.XQueryPointer.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
            C.POINTER(C.c_ulong), C.POINTER(C.c_int), C.POINTER(C.c_int),
            C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_uint)]
        x.XFree.argtypes = [C.c_void_p]
        self.error = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)(lambda *_: 0)
        x.XSetErrorHandler.argtypes = [C.c_void_p]
        x.XSetErrorHandler(self.error)
        display_environment()
        self.display = x.XOpenDisplay(os.environ["DISPLAY"].encode())
        if not self.display:
            raise RuntimeError("Affichage X11/XWayland inaccessible")
        self.atom = x.XInternAtom(self.display, b"_NET_WM_PID", 0)

    def close(self):
        self.x.XCloseDisplay(self.display)

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

    def focused(self):
        window, revert = C.c_ulong(), C.c_int()
        self.x.XGetInputFocus(self.display, C.byref(window), C.byref(revert))
        for _ in range(12):
            if window.value <= 1:
                break
            pid = self.window_pid(window.value)
            if pid:
                return window.value, pid
            root, parent, children, count = C.c_ulong(), C.c_ulong(), C.c_void_p(), C.c_uint()
            status = self.x.XQueryTree(self.display, window, C.byref(root),
                                      C.byref(parent), C.byref(children), C.byref(count))
            if children:
                self.x.XFree(children)
            if not status or parent.value == window.value:
                break
            window = parent
        return 0, 0

    def owned(self):
        return self.has_launcher_ancestor(self.focused()[1])

    def pointer_inside(self, window):
        root, child = C.c_ulong(), C.c_ulong()
        x, y, root_x, root_y = C.c_int(), C.c_int(), C.c_int(), C.c_int()
        width, height, border, depth, mask = (C.c_uint() for _ in range(5))
        if not self.x.XGetGeometry(self.display, window, C.byref(root), C.byref(x),
                C.byref(y), C.byref(width), C.byref(height), C.byref(border), C.byref(depth)):
            return False
        if not self.x.XQueryPointer(self.display, window, C.byref(root), C.byref(child),
                C.byref(root_x), C.byref(root_y), C.byref(x), C.byref(y), C.byref(mask)):
            return False
        return 0 <= x.value < width.value and 0 <= y.value < height.value

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


def run_keyboard(launcher):
    import evdev

    deps = gtk_dependencies()
    Gtk, _, GLib, _ = deps
    focus = Focus(launcher)
    try:
        sender = KeySender(focus)
    except BaseException:
        focus.close()
        raise
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
        overlay = Overlay(deps, action)
        print("Clavier virtuel Minecraft prêt", flush=True)
        GLib.timeout_add(25, on_tick)
        Gtk.main()
    finally:
        for controller in devices.values():
            controller.device.close()
        sender.close()
        focus.close()


class LauncherPointer:
    def __init__(self, evdev):
        self.e = e = evdev.ecodes
        self.device = evdev.UInput({e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT],
                                    e.EV_REL: [e.REL_X, e.REL_Y]},
                                   name="Couchcraft Launcher Mouse")
        self.keyboard = None
        try:
            # Linux advertises the pointer and the keyboard as separate devices.
            self.keyboard = evdev.UInput({e.EV_KEY: [*range(1, 59), e.KEY_F8]},
                                        name="Couchcraft Launcher Keys")
        except Exception as error:
            print(f"Raccourci Start indisponible · {error}", flush=True)
        self.release_at = None
        self.owner = None
        self.remainder = [0.0, 0.0]

    def play(self, now):
        if self.keyboard is not None and self.release_at is None:
            self.keyboard.write(self.e.EV_KEY, self.e.KEY_F8, 1)
            self.release_at = now + .04
            self.keyboard.syn()

    def release_play(self):
        if self.release_at is not None:
            self.keyboard.write(self.e.EV_KEY, self.e.KEY_F8, 0)
            self.keyboard.syn()
            self.release_at = None

    def click(self, controller, pressed):
        if pressed and self.owner is None:
            self.owner = controller
        elif not pressed and self.owner is controller:
            self.owner = None
        else:
            return
        self.device.write(self.e.EV_KEY, self.e.BTN_LEFT, int(pressed))
        self.device.syn()

    def move(self, velocity, elapsed):
        moved = False
        for index, axis in enumerate((self.e.REL_X, self.e.REL_Y)):
            self.remainder[index] += velocity[index] * elapsed
            delta = int(self.remainder[index])
            if delta:
                self.device.write(self.e.EV_REL, axis, delta)
                self.remainder[index] -= delta
                moved = True
        if moved:
            self.device.syn()

    def reset(self):
        self.release_play()
        if self.owner is not None:
            self.click(self.owner, False)
        self.remainder[:] = [0.0, 0.0]

    def close(self):
        try:
            self.reset()
        finally:
            self.device.close()
            if self.keyboard is not None:
                self.keyboard.close()


def update_pointer(controllers, focus, pointer, window, armed, now, elapsed):
    if pointer.release_at is not None and now >= pointer.release_at:
        pointer.release_play()
    velocities = []
    for path, controller in list(controllers.items()):
        try:
            actions = controller.poll(now)
        except OSError:
            controller.device.close()
            controllers.pop(path)
            continue
        if not window:
            continue
        velocities.append(controller.pointer_velocity())
        for action in actions:
            if action == "release":
                pointer.click(controller, False)
            elif action == "press" and armed and focus.pointer_inside(window):
                pointer.click(controller, True)
            elif action == "play" and armed:
                pointer.play(now)
    if not window:
        pointer.reset()
        return False
    if pointer.owner and (pointer.owner not in controllers.values() or "b" not in pointer.owner.held):
        pointer.click(pointer.owner, False)
    velocity = max(velocities, key=lambda pair: math.hypot(*pair), default=(0.0, 0.0))
    pointer.move(velocity, elapsed)
    return armed or not any({"b", "start"} & controller.held for controller in controllers.values())


def run_mouse(launcher):
    import evdev

    focus = Focus(launcher)
    controllers = {}
    seen_devices = set()
    try:
        pointer = LauncherPointer(evdev)
        try:
            last_tick = time.monotonic()
            refresh_at = 0.0
            armed = was_focused = False
            print("Pointeur manette CLauncher prêt", flush=True)
            while os.getppid() == launcher:
                now = time.monotonic()
                if now >= refresh_at:
                    devices = set(evdev.list_devices())
                    candidates = devices - seen_devices if controllers else devices
                    discover(controllers, evdev, mouse=True, device_paths=candidates)
                    seen_devices = devices
                    refresh_at = now + 2.0
                window, pid = focus.focused()
                if pid != launcher:
                    window = 0
                if bool(window) != was_focused:
                    was_focused = bool(window)
                    print("CLauncher au premier plan" if window else "CLauncher en arrière-plan",
                          flush=True)
                sample = time.monotonic()
                attached = set(controllers)
                armed = update_pointer(controllers, focus, pointer, window, armed,
                                       sample, min(sample - last_tick, .05))
                # Retry a path if a read failed, even if it still exists in /dev/input.
                if lost := attached - controllers.keys():
                    seen_devices.difference_update(lost)
                    refresh_at = 0.0
                last_tick = sample
                interval = .01 if window else .10
                time.sleep(max(0.0, interval - (time.monotonic() - now)))
        finally:
            pointer.close()
    finally:
        for controller in controllers.values():
            controller.device.close()
        focus.close()


if __name__ == "__main__":
    mode, launcher = sys.argv[1:]
    try:
        {"clavier": run_keyboard, "souris": run_mouse}[mode](int(launcher))
    except (ImportError, OSError, RuntimeError, ValueError, ET.ParseError) as error:
        print(f"{mode.capitalize()} manette indisponible · {error}", file=sys.stderr)
        sys.exit(1)
