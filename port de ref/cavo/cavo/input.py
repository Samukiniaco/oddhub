"""CaVo — controles: teclado+mouse, TOUCH e GAMEPAD -> Intent.

Touch (P1): arrastar mira a ponta (360°); botões JATO (segura), PULO (aperta),
  AÇÃO (segura). Botões em coords do canvas (900x650), desenhados pelo game.
Gamepad (2 pads Xbox): stick DIREITO mira, RT/RB = jato, A = pulo, LB = ação,
  esquerdo-X gira (se o direito tá parado). Start/A/B navegam o menu (via main).
Tudo por injeção (pads e toques falsos) p/ testar sem hardware.
"""
import time
import sys
import json
import math

import pygame
from . import config as C
from .controlmap import defaults, key_down, layout_for_view

# botões touch em coords do canvas: (chave, x, y, raio, rótulo)
TOUCH_BUTTONS = [(key, *C.TOUCH_DEFAULT_LAYOUT[key], label) for key, label in
                 (("jet", "JATO"), ("flap", "PULO"), ("action", "AÇÃO"))]
STICK_DEAD = C.PAD_DEADZONE
AIM_RANGE = C.PAD_AIM_RANGE

_pads = []           # pygame Joystick (ou falsos no teste)
_browser_viewport = None


class Intent:
    def __init__(self, rotate=0.0, use_mouse=False, mouse_pos=(0, 0),
                 flap=False, jet=False, action=False):
        self.rotate = rotate
        self.use_mouse = use_mouse
        self.mouse_pos = mouse_pos
        self.flap = flap
        self.jet = jet
        self.action = action


class DeviceFocus:
    """O último dispositivo usado manda; pad neutro não devolve a mira ao mouse."""
    def __init__(self, mouse_pos=None):
        self.source = "mouse"
        self.mouse_pos = mouse_pos
        self.fingers = set()
        self.touch_time = -float("inf")

    def prepare(self, events):
        # SDL pode enfileirar o mouse sintético antes do FINGERDOWN.
        if any(e.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP) for e in events):
            self.touch_time = time.monotonic()

    def accepts_mouse(self, ev):
        return (not getattr(ev, "touch", False) and not self.fingers and
                time.monotonic() - self.touch_time > C.TOUCH_MOUSE_GUARD)

    def event(self, ev):
        if ev.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            self.touch_time = time.monotonic()
            if ev.type == pygame.FINGERUP:
                self.fingers.discard(ev.finger_id)
            else:
                self.fingers.add(ev.finger_id)
            self.source = "touch"
        elif ev.type == pygame.KEYDOWN:
            self.source = "keyboard"
        elif self.accepts_mouse(ev):
            if ev.type == pygame.MOUSEBUTTONDOWN:
                self.source = "mouse"
            elif ev.type == pygame.MOUSEMOTION:
                pos = getattr(ev, "pos", None)
                # SDL web pode mandar rel=(0,0) mesmo com movimento real.
                moved = any(getattr(ev, "rel", (0, 0))) or (
                    pos is not None and self.mouse_pos is not None and pos != self.mouse_pos)
                if moved:
                    self.source = "mouse"
                if pos is not None:
                    self.mouse_pos = pos

    def observe_pad(self, joy):
        if joy is not None and (any(_axis(joy, i) for i in range(4)) or
                                any(_btn(joy, i) for i in range(C.PAD_MAX_BUTTONS)) or
                                _axis(joy, 5) > 0 or any(_hat(joy))):
            self.source = "gamepad"


class BrowserPad:
    """Gamepad API standard -> layout usado pelo input (sem depender do SDL web)."""
    def __init__(self, snapshot):
        self.axes = snapshot.get("axes", [])
        self.buttons = snapshot.get("buttons", [])
        self.pressed_tokens = {f"b{i}" for i, v in enumerate(self.buttons) if v > 0.5}
        if len(self.buttons) > 7 and self.buttons[7] > 0.5:
            self.pressed_tokens.add("rt")

    def get_axis(self, i):
        if i == 5:
            return self.buttons[7] * 2 - 1 if len(self.buttons) > 7 else -1.0
        return self.axes[i] if i < len(self.axes) else 0.0

    def get_button(self, i):
        return i < len(self.buttons) and self.buttons[i] > 0.5

    def get_hat(self, i):
        return (int(self.get_button(15)) - int(self.get_button(14)),
                int(self.get_button(12)) - int(self.get_button(13)))


def poll_pads():
    """No browser, consulta snapshots padronizados a cada frame (inclui hotplug)."""
    global _browser_viewport
    if sys.platform == "emscripten":
        import platform
        raw = str(platform.window.cavoPollGamepads())
        if raw:
            data = json.loads(raw)
            snapshots = data["pads"]
            _browser_viewport = tuple(data["viewport"])
            set_pads([BrowserPad(p) for p in snapshots if p and p.get("connected")])
    return _pads


def browser_viewport():
    return _browser_viewport


class PadMenu:
    """Direcional/stick repetem com atraso; A/B/Start disparam só na borda."""
    def __init__(self):
        self.held = set()
        self.direction = None
        self.wait = 0.0

    def update(self, dt, joy, controls=None):
        pressed = set()
        direction = None
        if joy is not None:
            mapping = (controls or defaults())["gamepad"]
            tokens = pad_tokens(joy)
            if tokens.intersection(mapping["confirm"]):
                pressed.add(pygame.K_RETURN)
            if tokens.intersection(mapping["menu"]):
                pressed.add(pygame.K_PAUSE)
            if tokens.intersection(mapping["back"]):
                pressed.add(pygame.K_ESCAPE)
            reserved = set(mapping["confirm"] + mapping["back"] + mapping["menu"])
            if _btn(joy, 4) and "b4" not in reserved:
                pressed.add(pygame.K_PAGEUP)
            if _btn(joy, 5) and "b5" not in reserved:
                pressed.add(pygame.K_PAGEDOWN)
            hx, hy = _hat(joy)
            x = hx or _axis(joy, 0)
            y = -hy if hy else _axis(joy, 1)
            if max(abs(x), abs(y)) >= C.PAD_MENU_THRESHOLD:
                direction = (pygame.K_RIGHT if x > 0 else pygame.K_LEFT) if abs(x) > abs(y) else (
                    pygame.K_DOWN if y > 0 else pygame.K_UP)
        keys = sorted(pressed - self.held)
        self.held = pressed
        if direction != self.direction:
            self.direction = direction
            self.wait = C.PAD_MENU_DELAY
            if direction is not None:
                keys.insert(0, direction)
        elif direction is not None:
            self.wait -= dt
            if self.wait <= 0:
                keys.insert(0, direction)
                self.wait = C.PAD_MENU_REPEAT
        return keys


# ---------- touch ----------
class TouchControls:
    """Cada dedo mantém sua função até soltar. Mira nunca usa coordenadas do mundo."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.fingers = {}
        self.vector = None
        self.angle = 0.0
        self.mode = "joystick"

    @property
    def buttons(self):
        return {role for role, _pos in self.fingers.values() if role != "aim"}

    def event(self, kind, fid, pos, controls=None, angle=0.0, viewport=(C.W, C.H)):
        controls = controls or defaults()
        layout = layout_for_view(controls["touch_layout"], viewport)
        self.mode = controls["touch_mode"]
        if kind == "down":
            if fid in self.fingers:
                return None
            for role in ("menu", "jet", "flap", "action"):
                x, y, r = layout[role]
                if math.hypot(pos[0]-x, pos[1]-y) <= r:
                    self.fingers[fid] = (role, pos)
                    return role
            x, y, r = layout["aim"]
            if (not any(role == "aim" for role, _ in self.fingers.values()) and
                    math.hypot(pos[0]-x, pos[1]-y) <= r):
                self.fingers[fid] = ("aim", pos)
                self.angle = angle
                self._aim(pos, pos, layout)
                return "aim"
        elif fid in self.fingers:
            role, previous = self.fingers[fid]
            if kind == "up":
                del self.fingers[fid]
                if role == "aim":
                    self.vector = None
            elif kind == "move":
                self.fingers[fid] = (role, pos)
                if role == "aim":
                    self._aim(pos, previous, layout)
            return role
        return None

    def _aim(self, pos, previous, layout):
        if self.mode == "swipe":
            self.angle = (self.angle + (pos[0]-previous[0]) * C.TOUCH_SWIPE_SENS) % 360
            a = math.radians(self.angle)
            self.vector = (-math.sin(a), math.cos(a))
        else:
            x, y, r = layout["aim"]
            dx, dy = pos[0]-x, pos[1]-y
            length = math.hypot(dx, dy)
            self.vector = (dx/length, dy/length) if length > r*C.TOUCH_STICK_DEAD else None


_touch = TouchControls()


def touch_event(kind, fid, pos, controls=None, angle=0.0, viewport=(C.W, C.H)):
    return _touch.event(kind, fid, pos, controls, angle, viewport)


def touch_active():
    return bool(_touch.fingers)


def touch_state():
    return {"aim": _touch.vector, "btn": _touch.buttons}


def touch_reset():
    _touch.reset()


# ---------- gamepad ----------
def init_pads():
    try:
        pygame.joystick.init()
        _pads.clear()
        for i in range(pygame.joystick.get_count()):
            j = pygame.joystick.Joystick(i)
            j.init()
            _pads.append(j)
    except pygame.error:
        pass
    return _pads


def set_pads(pads):
    """Injeta pads (reais ou falsos) — teste e main usam."""
    _pads.clear()
    _pads.extend(pads)
    return _pads


def _axis(joy, i):
    try:
        v = float(joy.get_axis(i))
    except (pygame.error, IndexError, TypeError):
        return 0.0
    return v if abs(v) > STICK_DEAD else 0.0


def _btn(joy, i):
    try:
        return bool(joy.get_button(i))
    except (pygame.error, IndexError, TypeError):
        return False


def _hat(joy):
    try:
        return joy.get_hat(0)
    except (pygame.error, IndexError, AttributeError):
        return (0, 0)


def pad_tokens(joy):
    if joy is None:
        return set()
    if isinstance(joy, BrowserPad):
        return joy.pressed_tokens
    tokens = {f"b{i}" for i in range(C.PAD_MAX_BUTTONS) if _btn(joy, i)}
    if _axis(joy, 5) > 0:
        tokens.add("rt")
    return tokens


def pad_down(joy, bindings):
    return bool(pad_tokens(joy).intersection(bindings))


def pad_intent(joy, player_pos, controls=None):
    """Intent parcial do pad (só o que o stick/botões dizem)."""
    if joy is None:
        return Intent()
    controls = controls or defaults()
    aim, turn = (2, 0) if controls["aim_stick"] == "right" else (0, 2)
    rx, ry = _axis(joy, aim), _axis(joy, aim+1)
    lx = _axis(joy, turn)
    out = Intent()
    if rx or ry:
        out.use_mouse = True
        out.mouse_pos = (player_pos[0] + rx * AIM_RANGE, player_pos[1] + ry * AIM_RANGE)
    elif lx:
        out.rotate = max(-1.0, min(1.0, lx * 1.5))
    pressed = pad_tokens(joy)
    for action in ("jet", "flap", "action"):
        setattr(out, action, bool(pressed.intersection(controls["gamepad"][action])))
    return out


def _merge(base, extra):
    if extra.use_mouse:
        base.use_mouse = True
        base.mouse_pos = extra.mouse_pos
    elif extra.rotate:
        base.use_mouse = False
        base.rotate = extra.rotate
    base.flap = base.flap or extra.flap
    base.jet = base.jet or extra.jet
    base.action = base.action or extra.action
    return base


def _touch_intent(player_pos):
    if not touch_active():
        return Intent()
    out = Intent()
    if _touch.vector is not None:
        out.use_mouse = True
        out.mouse_pos = (player_pos[0]+_touch.vector[0]*AIM_RANGE,
                         player_pos[1]+_touch.vector[1]*AIM_RANGE)
    out.jet = "jet" in _touch.buttons
    out.flap = "flap" in _touch.buttons
    out.action = "action" in _touch.buttons
    return out


def read_intents(mode, keys, mbtn, mouse_pos, pads=None, player_pos=None, mouse_enabled=True,
                 controls=None, source=None):
    pads = pads if pads is not None else _pads
    p0 = player_pos[0] if player_pos else (0, 0)
    p1 = player_pos[1] if player_pos and len(player_pos) > 1 else (0, 0)
    m_left = mouse_enabled and bool(mbtn[0]) if len(mbtn) > 0 else False
    m_right = mouse_enabled and bool(mbtn[2]) if len(mbtn) > 2 else False
    pad0 = pads[0] if len(pads) > 0 else None
    pad1 = pads[1] if len(pads) > 1 else None
    controls = controls or defaults()
    mouse_enabled = mouse_enabled and source not in ("touch", "gamepad")
    m_left, m_right = m_left and mouse_enabled, m_right and mouse_enabled
    def keyboard(group, use_mouse=False):
        mapping = controls[group]
        rot = int(key_down(keys, mapping, "right")) - int(key_down(keys, mapping, "left"))
        return Intent(rotate=rot, use_mouse=use_mouse and rot == 0, mouse_pos=mouse_pos,
                      **{action: key_down(keys, mapping, action) for action in ("flap", "jet", "action")})
    i1 = keyboard("keyboard1", mouse_enabled)
    i1.jet |= m_left
    i1.action |= m_right
    if source in (None, "touch"):
        i1 = _merge(i1, _touch_intent(p0))
    if source in (None, "gamepad"):
        i1 = _merge(i1, pad_intent(pad0, p0, controls))
    if mode == "treino":
        return i1, None
    i2 = _merge(keyboard("keyboard2"), pad_intent(pad1, p1, controls))
    return i1, i2
