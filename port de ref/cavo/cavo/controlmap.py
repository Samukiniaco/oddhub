"""Mapas editáveis de controles e validação do settings (sem estado de partida)."""
import copy
import math
import pygame
from . import config as C

KEY_ACTIONS = ("left", "right", "flap", "jet", "action", "menu", "retry")
PAD_ACTIONS = ("flap", "jet", "action", "menu", "retry", "confirm", "back")


def defaults():
    return {
        "touch_mode": "joystick", "touch_layout": copy.deepcopy(C.TOUCH_DEFAULT_LAYOUT),
        "keyboard1": {"left": [pygame.K_a], "right": [pygame.K_d],
                      "flap": [pygame.K_SPACE, pygame.K_w], "jet": [pygame.K_s, pygame.K_f],
                      "action": [pygame.K_LSHIFT, pygame.K_e],
                      "menu": [pygame.K_ESCAPE, pygame.K_m], "retry": [pygame.K_r]},
        "keyboard2": {"left": [pygame.K_LEFT], "right": [pygame.K_RIGHT],
                      "flap": [pygame.K_UP], "jet": [pygame.K_DOWN],
                      "action": [pygame.K_RSHIFT, pygame.K_SLASH],
                      "menu": [], "retry": []},
        "gamepad": {"flap": ["b0"], "jet": ["b5", "rt"], "action": ["b4"],
                    "menu": ["b9"], "retry": ["b3"], "confirm": ["b0"], "back": ["b1"]},
        "aim_stick": "right",
        "layout_version": 3,
    }


def layout_valid(layout):
    try:
        for key in C.TOUCH_DEFAULT_LAYOUT:
            x, y, r = layout[key]
            if not all(math.isfinite(v) for v in (x, y, r)):
                return False
            if not (C.TOUCH_MIN_RADIUS <= r <= C.TOUCH_MAX_RADIUS and
                    r <= x <= C.W-r and r <= y <= C.H-r):
                return False
        keys = list(C.TOUCH_DEFAULT_LAYOUT)
        for i, a in enumerate(keys):
            x, y, r = layout[a]
            for b in keys[i+1:]:
                xx, yy, rr = layout[b]
                if math.hypot(x-xx, y-yy) < r+rr+C.TOUCH_LAYOUT_GAP:
                    return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def load_controls(data):
    out = defaults()
    if not isinstance(data, dict):
        return out
    for key, choices in (("touch_mode", ("joystick", "swipe")), ("aim_stick", ("left", "right"))):
        if data.get(key) in choices:
            out[key] = data[key]
    if isinstance(data.get("touch_layout"), dict) and layout_valid(data["touch_layout"]):
        out["touch_layout"] = {k: list(data["touch_layout"][k]) for k in C.TOUCH_DEFAULT_LAYOUT}
        if data.get("layout_version", 1) < 3 and out["touch_layout"]["menu"] in ([850, 100, 28], [450, 100, 28]):
            out["touch_layout"]["menu"] = list(C.TOUCH_DEFAULT_LAYOUT["menu"])
    for group in ("keyboard1", "keyboard2", "gamepad"):
        mapping = data.get(group)
        if not isinstance(mapping, dict):
            continue
        for action in out[group]:
            values = mapping.get(action)
            if not isinstance(values, list) or len(values) > 4:
                continue
            if group == "gamepad":
                valid = all(v == "rt" or (isinstance(v, str) and v.startswith("b") and
                            v[1:].isdigit() and 0 <= int(v[1:]) < C.PAD_MAX_BUTTONS) for v in values)
            else:
                valid = all(type(v) is int and 0 <= v < 2**31 and pygame.key.name(v) for v in values)
            if valid and (values or action not in ("confirm", "back", "menu")):
                out[group][action] = list(dict.fromkeys(values))
    return out


def key_down(keys, mapping, action):
    return any(keys[k] for k in mapping[action])


def layout_for_view(layout, size):
    """Posições normalizadas na tela toda; raios uniformes, sem zonas elípticas."""
    return {key: [x*size[0]/C.W, y*size[1]/C.H, r] for key, (x, y, r) in layout.items()}
