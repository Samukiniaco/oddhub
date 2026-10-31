"""Configuração de controles: captura de teclas/pad e editor touch por arraste."""
import copy
import math
import pygame
from . import config as C
from .controlmap import defaults, KEY_ACTIONS, PAD_ACTIONS, layout_valid, layout_for_view
from .input import pad_tokens
from .texts import T
from .graphics import draw


class ControlsMenu:
    def __init__(self, settings):
        self.st = settings
        self.page = "home"
        self.index = 0
        self.capture = None
        self.armed = False
        self.pad_latch = False
        self.rects = []
        self.draft = None
        self.selected = "aim"
        self.drag = None
        self.message = ""
        self.viewport = (C.W, C.H)

    def rows(self):
        controls = self.st.controls
        if self.page == "home":
            return [("touch_mode", T("controls.touch_mode"), T("controls."+controls["touch_mode"])),
                    ("layout", T("controls.layout"), ""),
                    ("keyboard1", T("controls.keyboard1"), ""),
                    ("keyboard2", T("controls.keyboard2"), ""),
                    ("gamepad", T("controls.gamepad"), ""),
                    ("reset", T("controls.reset"), ""), ("return", T("controls.back"), "")]
        if self.page == "layout":
            return []
        actions = PAD_ACTIONS if self.page == "gamepad" else KEY_ACTIONS
        rows = [(action, T("controls."+action), self.binding_label(controls[self.page][action]))
                for action in actions]
        if self.page == "gamepad":
            rows.append(("aim_stick", T("controls.aim_stick"), T("controls."+controls["aim_stick"])))
        return rows + [("reset", T("controls.reset"), ""), ("return", T("controls.back"), "")]

    def binding_label(self, values):
        if self.page != "gamepad":
            return " / ".join(pygame.key.name(v).upper() for v in values) or "—"
        names = {"b0": "A", "b1": "B", "b2": "X", "b3": "Y", "b4": "LB",
                 "b5": "RB", "b6": "LT", "b7": "RT", "b8": "View", "b9": "Start", "rt": "RT"}
        return " / ".join(names.get(v, v.upper()) for v in values) or "—"

    def back(self):
        if self.capture:
            self.capture = None
        elif self.page != "home":
            self.page, self.index, self.drag = "home", 0, None
            self.draft = None
        else:
            return False
        self.message = ""
        return True

    def activate(self):
        action = self.rows()[self.index][0]
        if action == "return":
            return self.back()
        if action == "reset":
            if self.page == "home":
                self.st.controls = defaults()
            else:
                self.st.controls[self.page] = defaults()[self.page]
                if self.page == "gamepad":
                    self.st.controls["aim_stick"] = "right"
            self.st.save()
        elif action in ("touch_mode", "aim_stick"):
            choices = ("joystick", "swipe") if action == "touch_mode" else ("right", "left")
            self.st.controls[action] = choices[1-choices.index(self.st.controls[action])]
            self.st.save()
        elif self.page == "home":
            self.page, self.index = action, 0
            if action == "layout":
                self.draft = copy.deepcopy(self.st.controls["touch_layout"])
                self.selected = "aim"
        else:
            self.capture, self.armed = action, False
        return True

    def key(self, key):
        if key == pygame.K_ESCAPE:
            return self.back()
        if self.capture:
            if self.page != "gamepad" and key != pygame.K_F11:
                self.assign(key)
            return True
        if self.page == "layout":
            if key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.resize(1)
            elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.resize(-1)
            elif key == pygame.K_RETURN:
                self.save_layout()
            return True
        if key == pygame.K_UP:
            self.index = (self.index-1) % len(self.rows())
        elif key == pygame.K_DOWN:
            self.index = (self.index+1) % len(self.rows())
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT):
            if key in (pygame.K_RETURN, pygame.K_SPACE) or self.rows()[self.index][0] in ("touch_mode", "aim_stick"):
                return self.activate()
        return True

    def assign(self, binding):
        action = self.capture
        mapping = self.st.controls[self.page]
        previous = list(mapping[action])
        # Confirmar/voltar no menu podem compartilhar botões com ações da partida.
        group = ("confirm", "back") if action in ("confirm", "back") else KEY_ACTIONS
        for other in group:
            if other != action and other in mapping:
                remaining = [v for v in mapping[other] if v != binding]
                mapping[other] = remaining or (previous if binding in mapping[other] else [])
        mapping[action] = [binding]
        self.pad_latch = self.page == "gamepad"
        self.capture = None
        self.st.save()

    def capture_pad(self, joy):
        if self.pad_latch:
            if not pad_tokens(joy):
                self.pad_latch = False
            return True
        if not self.capture or self.page != "gamepad":
            return bool(self.capture)
        pressed = pad_tokens(joy)
        if not pressed:
            self.armed = True
        elif self.armed:
            self.assign("rt" if "rt" in pressed else sorted(pressed)[0])
        return True

    def hover(self, pos):
        if not self.capture and self.page != "layout":
            for i, rect in self.rects:
                if rect.collidepoint(pos):
                    self.index = i

    def pointer(self, kind, fid, pos):
        if self.capture:
            if kind == "down" and pygame.Rect(300, 475, 300, 50).collidepoint(pos):
                self.capture = None
            return True
        if self.page != "layout":
            if kind == "down":
                for i, rect in self.rects:
                    if rect.collidepoint(pos):
                        self.index = i
                        return self.activate()
            return True
        if kind == "down":
            if pos[1] < 65:
                if pos[0] < 160:
                    self.save_layout()
                elif pos[0] < 330:
                    self.draft = copy.deepcopy(C.TOUCH_DEFAULT_LAYOUT)
                elif pos[0] < 500:
                    self.back()
                elif pos[0] > self.viewport[0]-180:
                    self.resize(1 if pos[0] > self.viewport[0]-90 else -1)
                return True
            for name, (x, y, r) in layout_for_view(self.draft, self.viewport).items():
                if math.hypot(pos[0]-x, pos[1]-y) <= r:
                    self.selected = name
                    self.drag = (fid, pos[0]-x, pos[1]-y)
                    break
        elif self.drag and self.drag[0] == fid:
            if kind == "up":
                self.drag = None
            elif kind == "move":
                r = self.draft[self.selected][2]
                rx, ry = self.viewport[0]/C.W, self.viewport[1]/C.H
                x = max(r*rx, min((C.W-r)*rx, pos[0]-self.drag[1]))
                y = max(max(70+r, r*ry), min((C.H-r)*ry, pos[1]-self.drag[2]))
                self.draft[self.selected][:2] = [x/rx, y/ry]
        return True

    def resize(self, direction):
        x, y, r = self.draft[self.selected]
        r = max(C.TOUCH_MIN_RADIUS, min(C.TOUCH_MAX_RADIUS, r+direction*C.TOUCH_SIZE_STEP))
        self.draft[self.selected] = [max(r, min(C.W-r, x)), max(70+r, min(C.H-r, y)), r]

    def save_layout(self):
        if layout_valid(self.draft):
            self.st.controls["touch_layout"] = copy.deepcopy(self.draft)
            self.st.save()
            self.back()
        else:
            self.message = T("controls.overlap")

    def draw(self, surface, game, tabbed=False):
        surface.fill(C.BG)
        if self.page == "layout":
            self.viewport = surface.get_size()
            for text, rect in (("save", (10, 10, 145, 48)), ("reset", (170, 10, 155, 48)),
                               ("cancel", (340, 10, 155, 48))):
                draw.rect(surface, (45, 65, 100), rect, border_radius=8)
                game.txt_fit(surface, T("controls."+text), rect[2]-10, 20, C.WHITE,
                             rect[0]+rect[2]//2, rect[1]+rect[3]//2)
            for x, label in ((self.viewport[0]-140, "−"), (self.viewport[0]-50, "+")):
                draw.rect(surface, (45, 65, 100), (x-35, 10, 70, 48), border_radius=8)
                game.txt(surface, label, game.font, C.WHITE, x, 34)
            draw_touch(surface, game, self.draft, self.selected)
            game.txt_fit(surface, self.message or T("controls.drag"), self.viewport[0]-60,
                         20, C.YELLOW, self.viewport[0]/2, self.viewport[1]/2)
            return
        game.txt_fit(surface, T("controls."+self.page), C.W-80, 30, C.CYAN, C.W//2, 80 if tabbed else 45)
        self.rects = []
        rows = self.rows()
        height = min(58, 475//len(rows))
        for i, (_action, label, value) in enumerate(rows):
            rect = pygame.Rect(75, (110 if tabbed else 90)+i*height, 750, height-5)
            self.rects.append((i, rect))
            draw.rect(surface, (45, 75, 135) if i == self.index else (27, 36, 58), rect, border_radius=8)
            game.txt_fit(surface, label, 360, 22, C.WHITE, 280, rect.centery)
            game.txt_fit(surface, value, 325, 20, C.YELLOW, 640, rect.centery)
        if not tabbed:
            game.txt_fit(surface, T("controls.hint"), C.W-40, 18, C.WHITE, C.W//2, 620)
        if self.capture:
            shade = pygame.Surface((C.W, C.H), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 210))
            surface.blit(shade, (0, 0))
            message = T("controls.capture_pad" if self.page == "gamepad" else "controls.capture_key")
            game.txt_fit(surface, message, C.W-70, 25, C.YELLOW, C.W//2, 300)
            draw.rect(surface, (45, 65, 100), (300, 475, 300, 50), border_radius=8)
            game.txt(surface, T("controls.cancel"), game.font, C.WHITE, 450, 500)


def draw_touch(surface, game, layout, selected=None):
    from .input import touch_state
    state = touch_state()
    editing = selected is not None
    cache = getattr(game, "_touch_art", None)
    if cache is None:
        cache = game._touch_art = {}
    for key, (x, y, r) in layout_for_view(layout, surface.get_size()).items():
        aim = key == "aim"
        if aim and not editing and game.st.controls["touch_mode"] == "swipe":
            continue  # área invisível em jogo; editor mostra o contato
        r = int(r)
        active = key in state["btn"] or key == selected
        label = "swipe" if aim and game.st.controls["touch_mode"] == "swipe" else key
        label = T("controls."+label) if not aim or editing else ""
        token = (key, r, active, editing, label)
        image = cache.get(token)
        if image is None:
            if len(cache) >= 96:
                cache.clear()
            image = pygame.Surface((r*2+6, r*2+6), pygame.SRCALPHA)
            center = (r+3, r+3)
            if not aim or editing:
                color = (90, 200, 255, 150) if active else (80, 100, 145, 95)
                pygame.draw.circle(image, color, center, r)
            alpha = C.TOUCH_BORDER_ALPHA if aim and not editing else 180
            pygame.draw.circle(image, (210, 230, 255, alpha), center, r, 2)
            if label:
                game.txt_fit(image, label, r*2-8, 18, C.WHITE, *center)
            cache[token] = image
        image.set_alpha(255 if editing else round(255*game.st.touch_opacity))
        surface.blit(image, (int(x)-r-3, int(y)-r-3))
        if aim and state["aim"] and not editing:
            dx, dy = state["aim"]
            radius = max(4, int(r*.3))
            knob = cache.get(("knob", radius))
            if knob is None:
                knob = pygame.Surface((radius*2+6, radius*2+6), pygame.SRCALPHA)
                pygame.draw.circle(knob, (210, 230, 255, C.TOUCH_KNOB_ALPHA),
                                   (radius+3, radius+3), radius, 2)
                cache[("knob", radius)] = knob
            knob.set_alpha(round(255*game.st.touch_opacity))
            surface.blit(knob, (int(x+dx*r*.6)-radius-3, int(y+dy*r*.6)-radius-3))
