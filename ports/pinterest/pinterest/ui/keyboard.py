"""Teclado virtual navegável por controle, teclado físico e mouse."""
from __future__ import annotations

from typing import Callable, Optional

import pygame

from .. import config
from .widgets import FontBook, draw_round_rect, draw_text, truncate


class _Key:
    __slots__ = ("label", "action", "weight", "kind")

    def __init__(self, label: str, action: str, weight: float = 1.0, kind: str = "char"):
        self.label = label
        self.action = action
        self.weight = weight
        self.kind = kind


def _char(label: str, weight: float = 1.0) -> _Key:
    return _Key(label, label, weight, "char")


def _act(label: str, action: str, weight: float = 1.0) -> _Key:
    return _Key(label, action, weight, "action")


class OnScreenKeyboard:
    def __init__(self, fonts: FontBook):
        self.fonts = fonts
        self.active = False
        self.title = ""
        self.text = ""
        self.page = "abc"
        self.shift = False
        self.focus_row = 0
        self.focus_col = 0
        self.max_len = 2000
        self._confirm: Optional[Callable[[str], None]] = None
        self._cancel: Optional[Callable[[], None]] = None
        self._key_rects: list[tuple[pygame.Rect, _Key]] = []
        self._layout_size = (0, 0)
        self._panel = pygame.Rect(0, 0, 0, 0)
        self._field = pygame.Rect(0, 0, 0, 0)
        self._dim_cache: Optional[pygame.Surface] = None

    def open(
        self,
        title: str,
        text: str,
        on_confirm: Callable[[str], None],
        on_cancel: Optional[Callable[[], None]] = None,
        max_len: int = 2000,
    ) -> None:
        self.active = True
        self.title = title
        self.text = text or ""
        self.page = "abc"
        self.shift = False
        self.focus_row = 0
        self.focus_col = 0
        self.max_len = max_len
        self._confirm = on_confirm
        self._cancel = on_cancel

    def close(self) -> None:
        self.active = False
        self._confirm = None
        self._cancel = None

    def confirm(self) -> None:
        text = self.text
        cb = self._confirm
        self.close()
        if cb:
            cb(text)

    def cancel(self) -> None:
        cb = self._cancel
        self.close()
        if cb:
            cb()

    def _rows(self) -> list[list[_Key]]:
        if self.page == "123":
            return [
                [_char(c) for c in "1234567890"],
                [_char(c) for c in "-/:;()R$&@\""],
                [_act("#+=", "page:sym", 1.3), _char("."), _char(","), _char("?"),
                 _char("!"), _char("'"), _char("*"), _char("+"), _act("Back", "backspace", 1.4)],
                [_act("ABC", "page:abc", 1.3), _act("ESPAÇO", "space", 5.0),
                 _char("."), _act("ENTER", "enter", 1.6)],
                [_act("LIMPAR", "clear", 1.5), _act("CANCELAR", "cancel", 2.0)],
            ]
        if self.page == "sym":
            return [
                [_char(c) for c in "[]{}<=+%^".replace(" ", "")],
                [_char(c) for c in "_\\|~`§ªº€£"],
                [_act("áé", "page:acc", 1.3), _char("$"), _char("°"), _char("©"),
                 _char("®"), _char("™"), _char("•"), _char("–"),
                 _act("Back", "backspace", 1.4)],
                [_act("ABC", "page:abc", 1.3), _act("ESPAÇO", "space", 5.0),
                 _char("."), _act("ENTER", "enter", 1.6)],
                [_act("LIMPAR", "clear", 1.5), _act("CANCELAR", "cancel", 2.0)],
            ]
        if self.page == "acc":
            return [
                [_char(c) for c in "áàâãéêíóôõ"],
                [_char(c) for c in "úüçÁÀÂÃÉÊÍ"],
                [_act("ABC", "page:abc", 1.3), _char("Ó"), _char("Ô"), _char("Õ"),
                 _char("Ú"), _char("Ü"), _char("Ç"), _char("ñ"), _char("Ñ"),
                 _act("Back", "backspace", 1.4)],
                [_act("123", "page:123", 1.3), _act("ESPAÇO", "space", 5.0),
                 _char("."), _act("ENTER", "enter", 1.6)],
                [_act("LIMPAR", "clear", 1.5), _act("CANCELAR", "cancel", 2.0)],
            ]
        # abc
        if self.shift:
            rows = [
                [_char(c.upper()) for c in "qwertyuiop"],
                [_char(c.upper()) for c in "asdfghjklç"],
                [_act("Shift", "shift", 1.4)] + [_char(c.upper()) for c in "zxcvbnm"]
                + [_act("Back", "backspace", 1.4)],
            ]
        else:
            rows = [
                [_char(c) for c in "qwertyuiop"],
                [_char(c) for c in "asdfghjklç"],
                [_act("Shift", "shift", 1.4)] + [_char(c) for c in "zxcvbnm"]
                + [_act("Back", "backspace", 1.4)],
            ]
        rows.append(
            [_act("123", "page:123", 1.3), _act("ESPAÇO", "space", 5.0),
             _char("."), _act("ENTER", "enter", 1.6)]
        )
        rows.append([_act("LIMPAR", "clear", 1.5), _act("CANCELAR", "cancel", 2.0)])
        return rows

    def _layout(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        self._layout_size = (w, h)
        margin = 18
        panel_w = min(w - 2 * margin, 900)
        panel_h = min(h - 24, 372 if h >= 540 else 330)
        panel_x = (w - panel_w) // 2
        panel_y = h - panel_h
        self._panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        inner_x = panel_x + 16
        inner_w = panel_w - 32
        title_h = 24
        field_h = 42
        field_y = panel_y + 10 + title_h
        self._field = pygame.Rect(inner_x, field_y, inner_w, field_h)

        rows = self._rows()
        top = self._field.bottom + 8
        bottom_hint = 18
        avail = panel_y + panel_h - 8 - bottom_hint - top
        gap = 6
        row_h = max(28, (avail - gap * (len(rows) - 1)) // len(rows))

        self._key_rects = []
        y = top
        for row in rows:
            total = sum(k.weight for k in row) or 1.0
            usable = inner_w - gap * (len(row) - 1)
            x = inner_x
            for key in row:
                kw = int(usable * (key.weight / total))
                rect = pygame.Rect(x, y, max(20, kw), row_h)
                self._key_rects.append((rect, key))
                x += kw + gap
            y += row_h + gap

    def _dim(self, surface: pygame.Surface) -> pygame.Surface:
        size = surface.get_size()
        if self._dim_cache is None or self._dim_cache.get_size() != size:
            self._dim_cache = pygame.Surface(size, pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 150))
        return self._dim_cache

    def _press(self, key: _Key) -> None:
        action = key.action
        if action == "enter":
            self.confirm()
        elif action == "cancel":
            self.cancel()
        elif action == "backspace":
            self.text = self.text[:-1]
        elif action == "space":
            self._insert(" ")
        elif action == "clear":
            self.text = ""
        elif action == "shift":
            self.shift = not self.shift
        elif action.startswith("page:"):
            self.page = action.split(":", 1)[1]
            self.focus_row = 0
            self.focus_col = 0
        else:
            self._insert(action)
            if self.shift and self.page == "abc":
                self.shift = False

    def _insert(self, value: str) -> None:
        if len(self.text) < self.max_len:
            self.text += value

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE,):
                self.cancel()
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm()
                return True
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            if event.key == pygame.K_UP:
                self.focus_row = max(0, self.focus_row - 1)
                self.focus_col = min(self.focus_col, len(self._rows()[self.focus_row]) - 1)
                return True
            if event.key == pygame.K_DOWN:
                self.focus_row = min(len(self._rows()) - 1, self.focus_row + 1)
                self.focus_col = min(self.focus_col, len(self._rows()[self.focus_row]) - 1)
                return True
            if event.key == pygame.K_LEFT:
                self.focus_col = max(0, self.focus_col - 1)
                return True
            if event.key == pygame.K_RIGHT:
                self.focus_col = min(len(self._rows()[self.focus_row]) - 1, self.focus_col + 1)
                return True
            if event.unicode and event.unicode.isprintable():
                mods = pygame.key.get_mods()
                if not (mods & (pygame.KMOD_CTRL | pygame.KMOD_ALT)):
                    self._insert(event.unicode)
                    return True
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, key in self._key_rects:
                if rect.collidepoint(event.pos):
                    self._press(key)
                    return True
        if event.type == pygame.MOUSEMOTION:
            for r, key in self._key_rects:
                if r.collidepoint(event.pos):
                    for ri, row in enumerate(self._rows()):
                        if key in row:
                            self.focus_row = ri
                            self.focus_col = row.index(key)
                            break
                    break
        return False

    def draw(self, surface: pygame.Surface, now: float) -> None:
        if not self.active:
            return
        if self._layout_size != surface.get_size():
            self._layout(surface)
        surface.blit(self._dim(surface), (0, 0))

        panel = self._panel
        draw_round_rect(surface, config.PANEL, panel, radius=16)
        pygame.draw.rect(surface, config.DIVIDER, pygame.Rect(panel.x, panel.y, panel.width, 1))

        f_title = self.fonts.get(15, True)
        f_text = self.fonts.get(19)
        f_key = self.fonts.get(16 if panel.height > 340 else 14, False)
        f_key_small = self.fonts.get(12)
        f_hint = self.fonts.get(12)

        draw_text(surface, self.title or "Digitar", (panel.x + 16, panel.y + 10), f_title, config.TEXT)
        draw_text(
            surface,
            f"{len(self.text)}/{self.max_len}",
            (panel.right - 16, panel.y + 10),
            f_hint,
            config.TEXT_DIM,
            anchor="topright",
        )

        draw_round_rect(surface, config.BG, self._field, radius=8)
        pygame.draw.rect(surface, config.DIVIDER, self._field, width=1, border_radius=8)
        shown = truncate(f_text, self.text + ("|" if int(now * 2) % 2 == 0 else " "), self._field.width - 20)
        draw_text(surface, shown, (self._field.x + 10, self._field.y + 9), f_text, config.TEXT)

        rows = self._rows()
        focused = None
        if 0 <= self.focus_row < len(rows):
            row = rows[self.focus_row]
            if 0 <= self.focus_col < len(row):
                focused = row[self.focus_col]

        for rect, key in self._key_rects:
            is_focus = key is focused
            is_action = key.kind == "action"
            if key.action == "enter":
                bg = config.ACCENT
                fg = config.WHITE
            elif key.action == "cancel":
                bg = (44, 44, 44)
                fg = config.TEXT_DIM
            elif key.action == "shift" and self.shift:
                bg = config.ACCENT_DARK
                fg = config.WHITE
            elif is_action:
                bg = (44, 44, 44)
                fg = config.TEXT
            else:
                bg = config.PANEL_2
                fg = config.TEXT
            if is_focus:
                bg = config.SELECT_STRONG
                fg = config.WHITE
            draw_round_rect(surface, bg, rect, radius=7)
            if is_focus:
                pygame.draw.rect(surface, config.WHITE, rect, width=2, border_radius=7)
            font = f_key if len(key.label) <= 3 else f_key_small
            draw_text(surface, key.label, rect.center, font, fg, anchor="center")

        hint = "Setas: navegar · Enter/A: selecionar · Esc/B: cancelar · digite no teclado físico"
        draw_text(
            surface,
            truncate(f_hint, hint, panel.width - 32),
            (panel.centerx, panel.bottom - 14),
            f_hint,
            config.TEXT_DIM,
            anchor="midbottom",
        )
