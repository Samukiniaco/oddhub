"""Teclado virtual navegavel pelo controle (setas), mouse ou teclado fisico.

Existe porque o teclado virtual do sistema (OmniOSK) nao vem no pacote padrao
do PortMaster; este funciona sem nenhuma dependencia extra. O campo de texto
tambem aceita pygame.TEXTINPUT, entao um teclado fisico, ou um OSK do sistema
precarregado no processo, escreve no campo normalmente.
"""
from __future__ import annotations

from typing import Callable, Optional

import pygame

from .widgets import FontBook, draw_round_rect, draw_text, get_theme, truncate


class _Key:
    __slots__ = ("label", "action", "weight", "kind")

    def __init__(self, label: str, action: str, weight: float = 1.0, kind: str = "char"):
        self.label = label
        self.action = action
        self.weight = weight
        self.kind = kind


def _char(label: str) -> _Key:
    return _Key(label, label, 1.0, "char")


def _act(label: str, action: str, weight: float = 1.0) -> _Key:
    return _Key(label, action, weight, "action")


class OnScreenKeyboard:
    """Teclado virtual simples, em camadas de letras, numeros e simbolos."""

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
        self._keys: list[tuple[pygame.Rect, _Key]] = []
        self._panel = pygame.Rect(0, 0, 0, 0)
        self._field = pygame.Rect(0, 0, 0, 0)
        self._size = (0, 0)

    # -- API ----------------------------------------------------------------
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
        callback = self._confirm
        self.close()
        if callback:
            callback(text)

    def cancel(self) -> None:
        callback = self._cancel
        self.close()
        if callback:
            callback()

    def insert(self, value: str) -> None:
        if len(self.text) < self.max_len:
            self.text += value

    def backspace(self) -> None:
        self.text = self.text[:-1]

    # -- layout -------------------------------------------------------------
    def _rows(self) -> list[list[_Key]]:
        if self.page == "123":
            return [
                [_char(c) for c in "1234567890"],
                [_char(c) for c in "-/:;()@$."],
                [_act("ABC", "page:abc", 1.4), _char(","), _char("!"), _char("?"),
                 _char("'"), _char("*"), _act("DEL", "backspace", 1.4)],
                [_act("SYM", "page:sym", 1.4), _act("SPACE", "space", 4.0),
                 _act("DEL", "backspace", 1.4), _act("OK", "enter", 1.6)],
                [_act("CLEAR", "clear", 1.6), _act("CANCEL", "cancel", 2.0)],
            ]
        if self.page == "sym":
            return [
                [_char(c) for c in "[]{}<>#%&"],
                [_char(c) for c in "_\\|~`+=_"],
                [_act("ABC", "page:abc", 1.4), _char("^"), _char("€"), _char("°"),
                 _char("©"), _act("DEL", "backspace", 1.4)],
                [_act("123", "page:123", 1.4), _act("SPACE", "space", 4.0),
                 _act("DEL", "backspace", 1.4), _act("OK", "enter", 1.6)],
                [_act("CLEAR", "clear", 1.6), _act("CANCEL", "cancel", 2.0)],
            ]
        letters = "abcdefghijklmnopqrstuvwxyz"
        if self.shift:
            letters = letters.upper()
        return [
            [_char(c) for c in letters[0:10]],
            [_char(c) for c in letters[10:20]],
            [_act("SHIFT", "shift", 1.5)]
            + [_char(c) for c in letters[20:26]]
            + [_act("DEL", "backspace", 1.5)],
            [
                _act("123", "page:123", 1.5),
                _act("SPACE", "space", 4.0),
                _act("OK", "enter", 1.6),
            ],
            [_act("CLEAR", "clear", 1.6), _act("CANCEL", "cancel", 2.0)],
        ]

    def _layout(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        self._size = (width, height)
        margin = 12
        panel_w = min(width - 2 * margin, 620)
        panel_h = min(height - 20, 330)
        panel_x = (width - panel_w) // 2
        panel_y = height - panel_h
        self._panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        inner_x = panel_x + 12
        inner_w = panel_w - 24
        self._field = pygame.Rect(inner_x, panel_y + 30, inner_w, 34)

        rows = self._rows()
        top = self._field.bottom + 8
        avail = panel_y + panel_h - 24 - top
        gap = 5
        row_h = max(24, (avail - gap * (len(rows) - 1)) // len(rows))

        self._keys = []
        y = top
        for row in rows:
            total = sum(k.weight for k in row) or 1.0
            usable = inner_w - gap * (len(row) - 1)
            x = inner_x
            for key in row:
                kw = int(usable * (key.weight / total))
                rect = pygame.Rect(x, y, max(18, kw), row_h)
                self._keys.append((rect, key))
                x += kw + gap
            y += row_h + gap

    # -- eventos ------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Processa um evento. Devolve True se o teclado virtual consumiu."""
        if not self.active:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.cancel()
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm()
                return True
            if event.key == pygame.K_BACKSPACE:
                self.backspace()
                return True
            if event.key == pygame.K_UP:
                self._move(-1, 0)
                return True
            if event.key == pygame.K_DOWN:
                self._move(1, 0)
                return True
            if event.key == pygame.K_LEFT:
                self._move(0, -1)
                return True
            if event.key == pygame.K_RIGHT:
                self._move(0, 1)
                return True
            if event.key == pygame.K_F12:
                self.cancel()
                return True
            if event.unicode and event.unicode.isprintable():
                mods = pygame.key.get_mods()
                if not (mods & (pygame.KMOD_CTRL | pygame.KMOD_ALT)):
                    self.insert(event.unicode)
                    return True
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, key in self._keys:
                if rect.collidepoint(event.pos):
                    self._press(key)
                    return True
        return False

    def _move(self, drow: int, dcol: int) -> None:
        rows = self._rows()
        if not rows:
            return
        if drow:
            self.focus_row = max(0, min(len(rows) - 1, self.focus_row + drow))
        if dcol:
            self.focus_col = max(0, min(len(rows[self.focus_row]) - 1, self.focus_col + dcol))

    def _press(self, key: _Key) -> None:
        action = key.action
        if action == "enter":
            self.confirm()
        elif action == "cancel":
            self.cancel()
        elif action == "backspace":
            self.backspace()
        elif action == "space":
            self.insert(" ")
        elif action == "clear":
            self.text = ""
        elif action == "shift":
            self.shift = not self.shift
        elif action.startswith("page:"):
            self.page = action.split(":", 1)[1]
            self.focus_row = 0
            self.focus_col = 0
        else:
            self.insert(action)
            if self.shift and self.page == "abc":
                self.shift = False

    # -- desenho ------------------------------------------------------------
    def draw(self, surface: pygame.Surface, now: float) -> None:
        if not self.active:
            return
        theme = get_theme()
        if self._size != surface.get_size():
            self._layout(surface)

        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        surface.blit(dim, (0, 0))

        panel = self._panel
        draw_round_rect(surface, theme.panel, panel, radius=10)

        f_title = self.fonts.get(13, True)
        f_text = self.fonts.get(16)
        f_key = self.fonts.get(15)
        f_key_small = self.fonts.get(11)
        f_hint = self.fonts.get(10)

        draw_text(surface, self.title or "Digitar", (panel.x + 12, panel.y + 8), f_title, theme.text)
        draw_text(
            surface,
            f"{len(self.text)}/{self.max_len}",
            (panel.right - 12, panel.y + 9),
            f_hint,
            theme.text_faint,
            anchor="topright",
        )

        draw_round_rect(surface, theme.bg, self._field, radius=6)
        pygame.draw.rect(surface, theme.divider, self._field, width=1)
        cursor = "|" if int(now * 2) % 2 == 0 else " "
        draw_text(
            surface,
            truncate(f_text, self.text + cursor, self._field.width - 16),
            (self._field.x + 8, self._field.y + 8),
            f_text,
            theme.text,
        )

        rows = self._rows()
        focused = None
        if 0 <= self.focus_row < len(rows):
            row = rows[self.focus_row]
            if 0 <= self.focus_col < len(row):
                focused = row[self.focus_col]

        for rect, key in self._keys:
            is_focus = key is focused
            if key.action == "enter":
                bg, fg = theme.accent, theme.white
            elif key.action == "cancel":
                bg, fg = (44, 48, 56), theme.text_dim
            elif key.kind == "action":
                bg, fg = theme.panel_2, theme.text
            else:
                bg, fg = theme.panel_3, theme.text
            if key.action == "shift" and self.shift:
                bg = theme.accent_dark
                fg = theme.white
            if is_focus:
                bg = theme.select_strong
                fg = theme.white
            draw_round_rect(surface, bg, rect, radius=5)
            if is_focus:
                pygame.draw.rect(surface, theme.white, rect, width=2, border_radius=5)
            font = f_key if len(key.label) <= 2 else f_key_small
            draw_text(surface, key.label, rect.center, font, fg, anchor="center")

        draw_text(
            surface,
            "Setas: navegar · Enter: usar · Esc: cancelar",
            (panel.centerx, panel.bottom - 12),
            f_hint,
            theme.text_faint,
            anchor="midbottom",
        )
