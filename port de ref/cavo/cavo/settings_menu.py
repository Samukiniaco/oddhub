"""Tela única de configurações: abas Vídeo, Controles e Extras."""
import pygame
from . import config as C
from .texts import T
from .graphics import draw
from .settings import EXTRA_OPTIONS


class SettingsMenu:
    tabs = ("video", "controls", "extras")

    def __init__(self, game):
        self.game = game
        self.tab = 0
        self.header = True
        self.extra_index = 0
        self.rows = []
        self.tab_rects = [pygame.Rect(75+i*255, 8, 240, 42) for i in range(3)]
        self.back_rect = pygame.Rect(715, 594, 150, 42)
        self.top = {"video": 0, "extras": 0}
        self.gesture = None
        self.scroll_up = pygame.Rect(837, 110, 42, 42)
        self.scroll_down = pygame.Rect(837, 470, 42, 42)

    def options(self):
        if self.name == "video":
            keys = ("menu.row_video", "menu.row_res", "menu.row_part", "menu.row_shake",
                    "menu.row_bg", "settings.smooth", "settings.quality", "settings.particle_density",
                    "settings.bg_density", "settings.shake_strength", "settings.hud_scale",
                    "settings.touch_opacity", "menu.row_back")
            return [(T(key), self.game.gfx_value(i)) for i, key in enumerate(keys)]
        rows = []
        for key in EXTRA_OPTIONS:
            label = {"show_fps": "fps", "debug_stats": "stats"}.get(key, key)
            rows.append((T("extras."+label), T("settings.on" if getattr(self.game.st, key) else "settings.off")))
        return rows+[(T("menu.row_back"), "")]

    def index(self):
        return self.game.gi if self.name == "video" else self.extra_index

    def select(self, index):
        if self.name == "video":
            self.game.gi = index
        else:
            self.extra_index = index

    def ensure_visible(self):
        if self.name == "controls":
            return
        top, index = self.top[self.name], self.index()
        if index < top:
            top = index
        elif index >= top+C.SETTINGS_VISIBLE_ROWS:
            top = index-C.SETTINGS_VISIBLE_ROWS+1
        self.top[self.name] = max(0, min(len(self.options())-C.SETTINGS_VISIBLE_ROWS, top))

    def scroll(self, amount):
        if self.name == "controls" or self.editing:
            return
        top = max(0, min(len(self.options())-C.SETTINGS_VISIBLE_ROWS, self.top[self.name]+amount))
        self.top[self.name] = top
        self.select(max(top, min(top+C.SETTINGS_VISIBLE_ROWS-1, self.index())))
        self.header = False

    @property
    def name(self):
        return self.tabs[self.tab]

    @property
    def editing(self):
        return self.name == "controls" and (self.game.controls.capture or self.game.controls.page == "layout")

    def open(self):
        self.tab, self.header = 0, True
        self.game.controls.page, self.game.controls.index = "home", 0
        self.game.controls.capture = None

    def change_tab(self, direction):
        self.tab = (self.tab+direction) % len(self.tabs)
        self.header = True
        self.gesture = None
        self.rows = []

    def key(self, key):
        game = self.game
        if self.editing:
            return game.controls.key(key)
        if key == pygame.K_ESCAPE:
            if self.name == "controls" and game.controls.page != "home":
                return game.controls.back()
            return False
        if key in (pygame.K_TAB, pygame.K_PAGEDOWN, pygame.K_PAGEUP):
            self.change_tab(-1 if key == pygame.K_PAGEUP else 1)
            return True
        if self.header:
            if key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.change_tab(1 if key == pygame.K_RIGHT else -1)
            elif key in (pygame.K_DOWN, pygame.K_RETURN, pygame.K_SPACE):
                self.header = False
            return True
        index = game.controls.index if self.name == "controls" else (
            game.gi if self.name == "video" else self.extra_index)
        if key == pygame.K_UP and index == 0 and (self.name != "controls" or game.controls.page == "home"):
            self.header = True
            return True
        if self.name == "controls":
            return game.controls.key(key)
        count = len(self.options())
        if key in (pygame.K_UP, pygame.K_DOWN):
            index = (index+(1 if key == pygame.K_DOWN else -1)) % count
            self.select(index)
            self.ensure_visible()
        elif key in (pygame.K_HOME, pygame.K_END):
            self.select(0 if key == pygame.K_HOME else count-1)
            self.ensure_visible()
        elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE):
            return self.activate(index, -1 if key == pygame.K_LEFT else 1)
        return True

    def activate(self, index, direction=1):
        if self.name == "video":
            if index == len(self.options())-1:
                return False
            self.game.gfx_adjust(index, direction)
        elif self.name == "extras":
            if index == len(EXTRA_OPTIONS):
                return False
            st = self.game.st
            key = EXTRA_OPTIONS[index]
            setattr(st, key, not getattr(st, key))
            st.save()
        return True

    def hover(self, pos):
        if self.editing:
            return
        if self.name == "controls":
            self.game.controls.hover(pos)
            if any(rect.collidepoint(pos) for _i, rect in self.game.controls.rects):
                self.header = False
        for i, rect in self.rows:
            if rect.collidepoint(pos):
                self.header = False
                if self.name == "video":
                    self.game.gi = i
                else:
                    self.extra_index = i

    def pointer(self, kind, fid, pos):
        if self.editing:
            return self.game.controls.pointer(kind, fid, pos)
        if kind == "down":
            if self.back_rect.collidepoint(pos):
                self.gesture = None
                return False
            for i, rect in enumerate(self.tab_rects):
                if rect.collidepoint(pos):
                    self.tab, self.header = i, True
                    self.gesture = None
                    return True
        if self.name == "controls":
            if kind == "down" and any(rect.collidepoint(pos) for _i, rect in self.game.controls.rects):
                self.header = False
            return self.game.controls.pointer(kind, fid, pos)
        if kind == "down" and self.scroll_up.collidepoint(pos):
            self.scroll(-1)
            return True
        if kind == "down" and self.scroll_down.collidepoint(pos):
            self.scroll(1)
            return True
        if self.gesture and self.gesture[0] == fid:
            _fid, start, index, initial, dragged = self.gesture
            delta = start[1]-pos[1]
            dragged = dragged or abs(delta) > 14
            if kind == "move" and dragged:
                desired = initial+round(delta/C.SETTINGS_ROW_HEIGHT)
                self.scroll(desired-self.top[self.name])
                self.gesture = (fid, start, index, initial, True)
            elif kind == "up":
                self.gesture = None
                if not dragged:
                    return self.activate(index)
            return True
        if kind == "down":
            for i, rect in self.rows:
                if rect.collidepoint(pos):
                    self.header = False
                    self.select(i)
                    if fid == "mouse":
                        return self.activate(i)
                    self.gesture = (fid, pos, i, self.top[self.name], False)
                    return True
        return True

    def draw(self, surface):
        game = self.game
        self.rows = []
        if self.name == "controls":
            game.controls.draw(surface, game, tabbed=True)
            if self.editing:
                return
        else:
            surface.fill(C.BG)
            game.txt_fit(surface, T("settings."+self.name), C.W-80, 28, C.CYAN, C.W//2, 80)
            rows, index = self.options(), self.index()
            self.ensure_visible()
            top = self.top[self.name]
            for visible, i in enumerate(range(top, min(len(rows), top+C.SETTINGS_VISIBLE_ROWS))):
                label, value = rows[i]
                rect = pygame.Rect(75, 110+visible*C.SETTINGS_ROW_HEIGHT, 750, 53)
                self.rows.append((i, rect))
                active = i == index and not self.header
                draw.rect(surface, (45, 75, 135) if active else (27, 36, 58), rect, border_radius=8)
                game.txt_fit(surface, label, 360, 22, C.WHITE, 280, rect.centery)
                game.txt_fit(surface, value, 325, 20, C.YELLOW, 640, rect.centery)
            for rect, label in ((self.scroll_up, "↑"), (self.scroll_down, "↓")):
                draw.rect(surface, (45, 65, 100), rect, border_radius=8)
                game.txt(surface, label, game.font, C.WHITE, *rect.center)
            track = pygame.Rect(851, 160, 12, 300)
            draw.rect(surface, (30, 40, 65), track, border_radius=4)
            thumb_height = max(24, 300*C.SETTINGS_VISIBLE_ROWS/len(rows))
            progress = top/max(1, len(rows)-C.SETTINGS_VISIBLE_ROWS)
            draw.rect(surface, (110, 165, 220), (851, 160+progress*(300-thumb_height), 12, thumb_height), border_radius=4)
            game.txt_fit(surface, T("settings.scroll").format(first=top+1, last=min(len(rows), top+C.SETTINGS_VISIBLE_ROWS), total=len(rows)),
                         750, 17, C.CYAN, C.W/2, 548)
        for i, rect in enumerate(self.tab_rects):
            draw.rect(surface, (45, 75, 135) if i == self.tab else (27, 36, 58), rect, border_radius=8)
            if self.header and i == self.tab:
                draw.rect(surface, C.CYAN, rect, 2, border_radius=8)
            game.txt_fit(surface, T("settings."+self.tabs[i]), 220, 21, C.WHITE, *rect.center)
        draw.rect(surface, (40, 50, 80), self.back_rect, border_radius=8)
        game.txt_fit(surface, T("menu.row_back"), 140, 20, C.WHITE, *self.back_rect.center)
        game.txt_fit(surface, T("settings.hint"), 625, 16, C.WHITE, 350, 620)
