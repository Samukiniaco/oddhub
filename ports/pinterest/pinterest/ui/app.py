"""Aplicativo pygame do port Pinterest."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import pygame

from .. import config
from ..backend import make_backend
from ..models import Board, Pin, format_time, preview_text
from ..store import Store
from .keyboard import OnScreenKeyboard
from .widgets import (
    FontBook,
    Toast,
    clamp,
    draw_round_rect,
    draw_scrollbar,
    draw_text,
    draw_toast,
    make_thumb,
    star_points,
    truncate,
    wrap_text,
)


class App:
    HEADER_H = 56
    HINT_H = 26
    SEARCH_H = 44
    CARD_GAP = 8
    CARD_MARGIN = 8
    CAPTION_H = 42

    def __init__(
        self,
        backend_kind: Optional[str] = None,
        fullscreen: Optional[bool] = None,
        window_size: Optional[tuple[int, int]] = None,
        data_dir: Optional[Path] = None,
        headless: bool = False,
    ):
        pygame.init()
        pygame.font.init()
        self.headless = headless
        self.data_dir = Path(data_dir) if data_dir else config.data_dir()
        self.fullscreen = config.wants_fullscreen() if fullscreen is None else bool(fullscreen)
        self._window = self._create_window(window_size)
        self._actual_size = self._window.get_size()
        self.logical_size = config.logical_size_for(*self._actual_size)
        self.surface = pygame.Surface(self.logical_size)
        self.fonts = FontBook()

        self.store = Store(self.data_dir / "pins.sqlite3")
        saved = self.store.meta_get("backend", "demo")
        self.backend_kind = (backend_kind or saved or "demo").lower()
        if self.backend_kind not in ("demo", "api"):
            self.backend_kind = "demo"
        self.backend = make_backend(self.backend_kind, self.store, self.data_dir)
        self.backend.start()

        self.keyboard = OnScreenKeyboard(self.fonts)
        self.running = True
        self.view = "feed"                     # feed | pin | boards
        self.modal: Optional[str] = None       # settings | about
        self.selected_pin_id: Optional[str] = None
        self.list_index = 0
        self.pins: list[Pin] = []
        self.scroll = 0.0
        self.board_filter: Optional[str] = None
        self.saved_only = False
        self.search = ""
        self.search_active = False
        self.toast: Optional[Toast] = None
        self._hits: list[tuple[pygame.Rect, str]] = []
        self._thumb_cache: dict[tuple[str, int, int], pygame.Surface] = {}
        self._feed_layout_cache: Optional[tuple] = None
        self._feed_layout_key = None
        self._feed_version = 0
        self._pin_layout_cache: Optional[tuple] = None
        self._pin_layout_key = None
        self._last_refresh = 0.0
        self._settings_index = 0
        self._boards_index = 0
        self._mouse_pos = (0, 0)
        self._clock = pygame.time.Clock()
        self._joy = None
        self._joy_axis = (0, 0)

        self._init_joystick()
        self._load_feed()
        pygame.display.set_caption(f"{config.APP_NAME} — OddHub")

    # -- janela -------------------------------------------------------------
    def _create_window(self, size: Optional[tuple[int, int]]):
        w, h = size or config.window_size()
        if self.fullscreen and not self.headless:
            info = pygame.display.Info()
            fw = info.current_w if info.current_w and info.current_w > 0 else w
            fh = info.current_h if info.current_h and info.current_h > 0 else h
            try:
                return pygame.display.set_mode((fw, fh), pygame.FULLSCREEN)
            except pygame.error:
                pass
        flags = 0 if self.headless else pygame.RESIZABLE
        try:
            return pygame.display.set_mode((w, h), flags)
        except pygame.error:
            return pygame.display.set_mode((w, h))

    def _to_logical(self, pos: tuple[int, int]) -> tuple[int, int]:
        aw, ah = self._actual_size
        lw, lh = self.logical_size
        if aw <= 0 or ah <= 0:
            return pos
        return int(pos[0] * lw / aw), int(pos[1] * lh / ah)

    def _present(self) -> None:
        if self.headless:
            return
        aw, ah = self._window.get_size()
        if (aw, ah) != self.logical_size:
            try:
                scaled = pygame.transform.smoothscale(self.surface, (aw, ah))
            except (pygame.error, ValueError):
                scaled = pygame.transform.scale(self.surface, (aw, ah))
            self._window.blit(scaled, (0, 0))
        else:
            self._window.blit(self.surface, (0, 0))
        pygame.display.flip()

    def _init_joystick(self) -> None:
        try:
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self._joy = pygame.joystick.Joystick(0)
                self._joy.init()
        except Exception:
            self._joy = None

    # -- dados --------------------------------------------------------------
    def _load_feed(self) -> None:
        if self.search.strip():
            pins = self.backend.search(self.search.strip())
        else:
            pins = self.backend.pins(board_id=self.board_filter)
        if self.saved_only:
            pins = [p for p in pins if p.is_saved]
        self.pins = pins
        if self.list_index >= len(self.pins):
            self.list_index = max(0, len(self.pins) - 1)
        if self.selected_pin_id and not any(p.id == self.selected_pin_id for p in self.pins):
            if self.view == "pin":
                self.view = "feed"
            self.selected_pin_id = None
        self._feed_version += 1
        self._feed_layout_cache = None
        self._pin_layout_cache = None
        self._last_refresh = time.time()

    def _selected_pin(self) -> Optional[Pin]:
        if not self.selected_pin_id:
            return None
        for pin in self.pins:
            if pin.id == self.selected_pin_id:
                return pin
        return self.backend.pin(self.selected_pin_id)

    def _open_pin(self, pin_id: str) -> None:
        self.selected_pin_id = pin_id
        self.view = "pin"
        self.scroll = 0.0

    def _back(self) -> None:
        if self.keyboard.active:
            self.keyboard.cancel()
            return
        if self.modal:
            self.modal = None
            return
        if self.search_active or self.search:
            self.search = ""
            self.search_active = False
            self._load_feed()
            return
        if self.view == "pin":
            self.view = "feed"
            return
        if self.view == "boards":
            self.view = "feed"
            return
        if self.board_filter or self.saved_only:
            self.board_filter = None
            self.saved_only = False
            self._load_feed()
            return
        self.running = False

    def _open_search(self) -> None:
        self.keyboard.open("Pesquisar pins", self.search, self._set_search, max_len=100)

    def _set_search(self, text: str) -> None:
        self.search = text.strip()
        self.search_active = bool(self.search)
        self.list_index = 0
        self.scroll = 0.0
        self._load_feed()

    def _clear_filters(self) -> None:
        self.search = ""
        self.search_active = False
        self.board_filter = None
        self.saved_only = False
        self.list_index = 0
        self.scroll = 0.0
        self._load_feed()

    def _open_boards(self) -> None:
        self.view = "boards"
        boards = self.backend.boards()
        if self._boards_index >= len(boards):
            self._boards_index = 0

    def _select_board(self, board: Board) -> None:
        self.board_filter = board.id
        self.saved_only = False
        self.search = ""
        self.search_active = False
        self.view = "feed"
        self.list_index = 0
        self.scroll = 0.0
        self._load_feed()

    def _toggle_save(self) -> None:
        if not self.selected_pin_id:
            return
        self.backend.toggle_save(self.selected_pin_id)
        self._load_feed()
        pin = self._selected_pin()
        if pin:
            self._toast("Salvo nos seus pins!" if pin.is_saved else "Removido dos salvos.", "ok")

    def _toast(self, text: str, kind: str = "info") -> None:
        self.toast = Toast(text, kind)

    # -- settings -----------------------------------------------------------
    def _open_settings(self) -> None:
        self.modal = "settings"
        self._settings_index = 0

    def _settings_rows(self) -> list[dict]:
        stats = self.store.stats()
        return [
            {"label": "Backend", "value": self.backend.label, "action": "toggle_backend"},
            {"label": "Status", "value": self.backend.status_label(), "action": "none"},
            {"label": "Token API", "value": "configurado" if self.backend.get_token() else "ausente", "action": "token"},
            {"label": "Boards", "value": str(stats["boards"]), "action": "boards"},
            {"label": "Pins", "value": f"{stats['pins']} · {stats['saved']} salvos", "action": "none"},
            {"label": "Meus salvos", "value": "ver pins salvos", "action": "saved"},
            {"label": "Atualizar", "value": "Sincronizar agora", "action": "refresh"},
            {"label": "Buscar", "value": "Pesquisar pins", "action": "search"},
            {"label": "Sobre", "value": "Informações do port", "action": "about"},
            {"label": "Fechar", "value": "", "action": "close"},
        ]

    def _activate_setting(self, action: str) -> None:
        if action in ("none", ""):
            return
        if action == "toggle_backend":
            self._toggle_backend()
        elif action == "token":
            self.keyboard.open("Token da API Pinterest", self.backend.get_token(), self._set_token, max_len=300)
        elif action == "boards":
            self.modal = None
            self._open_boards()
        elif action == "saved":
            self.modal = None
            self._clear_filters()
            self.saved_only = True
            self._load_feed()
            self._toast("Mostrando pins salvos.", "info")
        elif action == "refresh":
            self.backend.refresh()
            self._toast("Sincronizando...", "info")
        elif action == "search":
            self.modal = None
            self._open_search()
        elif action == "about":
            self.modal = "about"
        elif action == "close":
            self.modal = None

    def _set_token(self, token: str) -> None:
        token = token.strip()
        if token:
            self.backend.set_token(token)
            self._toast("Token salvo.", "ok")
            if self.backend_kind != "api":
                self._switch_backend("api")
        else:
            self._toast("Token vazio, nada salvo.", "warn")

    def _toggle_backend(self) -> None:
        target = "api" if self.backend_kind == "demo" else "demo"
        if target == "api" and not self.backend.get_token():
            self.keyboard.open("Token da API Pinterest", "", self._set_token, max_len=300)
            return
        self._switch_backend(target)

    def _switch_backend(self, kind: str) -> None:
        try:
            self.backend.stop()
        except Exception:
            pass
        self.backend_kind = kind
        self.store.meta_set("backend", kind)
        self.backend = make_backend(kind, self.store, self.data_dir)
        self.backend.start()
        self.selected_pin_id = None
        self._load_feed()
        if kind == "api":
            self._toast("API real ativada. Sincronizando...", "info")
        else:
            self.modal = None
            self._toast("Modo demo ativado.", "ok")

    # -- eventos ------------------------------------------------------------
    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.VIDEORESIZE and not self.fullscreen and not self.headless:
                try:
                    self._window = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                    self._actual_size = self._window.get_size()
                    self.logical_size = config.logical_size_for(*self._actual_size)
                    self.surface = pygame.Surface(self.logical_size)
                    self._feed_layout_cache = None
                except pygame.error:
                    pass
                continue

            if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                event.pos = self._to_logical(event.pos)
                self._mouse_pos = event.pos

            if self.keyboard.active:
                if self.keyboard.handle_event(event):
                    continue

            if self.modal:
                if self._handle_modal_event(event):
                    continue

            if event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse(event)
            elif event.type == pygame.MOUSEWHEEL:
                self._handle_wheel(event)
            elif event.type in (pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION, pygame.JOYAXISMOTION):
                self._handle_joy(event)

    def _nav_feed(self, dx: int, dy: int) -> None:
        if not self.pins:
            return
        cols = self._columns()
        idx = self.list_index
        if dx:
            idx = clamp(idx + dx, 0, len(self.pins) - 1)
        if dy:
            idx = clamp(idx + dy * cols, 0, len(self.pins) - 1)
        self.list_index = int(idx)
        self._ensure_visible()

    def _handle_key(self, event: pygame.event.Event) -> None:
        key = event.key
        if key in (pygame.K_UP, pygame.K_KP8):
            if self.view == "feed":
                self._nav_feed(0, -1)
            elif self.view == "pin":
                self.scroll += 70
            elif self.view == "boards":
                self._boards_index = max(0, self._boards_index - 1)
        elif key in (pygame.K_DOWN, pygame.K_KP2):
            if self.view == "feed":
                self._nav_feed(0, 1)
            elif self.view == "pin":
                self.scroll -= 70
            elif self.view == "boards":
                boards = self.backend.boards()
                self._boards_index = min(max(0, len(boards) - 1), self._boards_index + 1)
        elif key in (pygame.K_LEFT, pygame.K_KP4):
            if self.view == "feed":
                self._nav_feed(-1, 0)
        elif key in (pygame.K_RIGHT, pygame.K_KP6):
            if self.view == "feed":
                self._nav_feed(1, 0)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.view == "feed":
                if self.pins:
                    self._open_pin(self.pins[self.list_index].id)
            elif self.view == "boards":
                boards = self.backend.boards()
                if 0 <= self._boards_index < len(boards):
                    self._select_board(boards[self._boards_index])
        elif key in (pygame.K_BACKSPACE, pygame.K_DELETE, pygame.K_ESCAPE):
            self._back()
        elif key == pygame.K_F1:
            self.modal = "about"
        elif key == pygame.K_SPACE and self.view == "pin":
            self._toggle_save()
        elif event.unicode and event.unicode.isprintable() and self.view == "feed":
            self.search_active = True
            self.search = event.unicode
            self._load_feed()
            self._open_search()

    def _handle_mouse(self, event: pygame.event.Event) -> None:
        pos = event.pos
        if event.button == 4:
            if self.view == "feed":
                self._nav_feed(0, -1)
            elif self.view == "pin":
                self.scroll += 90
            elif self.view == "boards":
                self._boards_index = max(0, self._boards_index - 1)
            return
        if event.button == 5:
            if self.view == "feed":
                self._nav_feed(0, 1)
            elif self.view == "pin":
                self.scroll -= 90
            elif self.view == "boards":
                boards = self.backend.boards()
                self._boards_index = min(max(0, len(boards) - 1), self._boards_index + 1)
            return
        if event.button != 1:
            return
        action = self._hit(pos)
        if not action:
            return
        if action.startswith("pin:"):
            self._open_pin(action.split(":", 1)[1])
        elif action.startswith("settings_row:"):
            idx = int(action.split(":", 1)[1])
            rows = self._settings_rows()
            if 0 <= idx < len(rows):
                self._settings_index = idx
                self._activate_setting(rows[idx]["action"])
        elif action.startswith("board:"):
            board_id = action.split(":", 1)[1]
            for b in self.backend.boards():
                if b.id == board_id:
                    self._select_board(b)
                    break
        elif action == "search":
            self._open_search()
        elif action == "clear_search":
            self._clear_filters()
        elif action == "boards":
            self._open_boards()
        elif action == "refresh":
            self.backend.refresh()
            self._toast("Sincronizando...", "info")
        elif action == "settings":
            self._open_settings()
        elif action == "back":
            self._back()
        elif action == "save":
            self._toggle_save()
        elif action == "clear_filter":
            self._clear_filters()

    def _handle_wheel(self, event: pygame.event.Event) -> None:
        if self.modal:
            return
        if self.view == "feed":
            self._nav_feed(0, -1 if event.y > 0 else 1)
        elif self.view == "pin":
            self.scroll += event.y * 60

    def _handle_joy(self, event: pygame.event.Event) -> None:
        if event.type == pygame.JOYBUTTONDOWN:
            button = event.button
            if button == 0:  # A
                if self.view == "feed":
                    if self.pins:
                        self._open_pin(self.pins[self.list_index].id)
                elif self.view == "boards":
                    boards = self.backend.boards()
                    if 0 <= self._boards_index < len(boards):
                        self._select_board(boards[self._boards_index])
                elif self.view == "pin":
                    self._toggle_save()
            elif button == 1:  # B
                self._back()
            elif button == 2:  # X
                if self.view == "feed":
                    self._open_search()
            elif button == 3:  # Y
                if self.view == "feed":
                    self._open_boards()
            elif button in (6, 7):  # Select/Start
                self._open_settings()
        elif event.type == pygame.JOYHATMOTION:
            x, y = event.value
            if y == 1:
                self._handle_joy_dpad(0, -1)
            elif y == -1:
                self._handle_joy_dpad(0, 1)
            elif x == -1:
                self._handle_joy_dpad(-1, 0)
            elif x == 1:
                self._handle_joy_dpad(1, 0)
        elif event.type == pygame.JOYAXISMOTION:
            ax = event.axis
            val = event.value
            if ax == 1:
                old = self._joy_axis[1]
                new = 1 if val > 0.55 else (-1 if val < -0.55 else 0)
                if new != old:
                    self._joy_axis = (self._joy_axis[0], new)
                    if new != 0:
                        self._handle_joy_dpad(0, new)
            elif ax == 0:
                old = self._joy_axis[0]
                new = 1 if val > 0.55 else (-1 if val < -0.55 else 0)
                if new != old:
                    self._joy_axis = (new, self._joy_axis[1])
                    if new != 0:
                        self._handle_joy_dpad(new, 0)

    def _handle_joy_dpad(self, dx: int, dy: int) -> None:
        if self.view == "feed":
            self._nav_feed(dx, dy)
        elif self.view == "pin":
            if dy == -1:
                self.scroll += 70
            elif dy == 1:
                self.scroll -= 70
        elif self.view == "boards":
            boards = self.backend.boards()
            if dy == -1:
                self._boards_index = max(0, self._boards_index - 1)
            elif dy == 1:
                self._boards_index = min(max(0, len(boards) - 1), self._boards_index + 1)

    def _handle_modal_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.modal = None
            return True
        if self.modal == "settings":
            if event.type == pygame.KEYDOWN:
                rows = self._settings_rows()
                if event.key in (pygame.K_UP, pygame.K_KP8):
                    self._settings_index = max(0, self._settings_index - 1)
                    return True
                if event.key in (pygame.K_DOWN, pygame.K_KP2):
                    self._settings_index = min(len(rows) - 1, self._settings_index + 1)
                    return True
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._activate_setting(rows[self._settings_index]["action"])
                    return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action = self._hit(event.pos)
                if action and action.startswith("settings_row:"):
                    idx = int(action.split(":", 1)[1])
                    self._settings_index = idx
                    rows = self._settings_rows()
                    if 0 <= idx < len(rows):
                        self._activate_setting(rows[idx]["action"])
                    return True
        elif self.modal == "about":
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.modal = None
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action = self._hit(event.pos)
                if action == "about_close":
                    self.modal = None
                    return True
        return False

    # -- update -------------------------------------------------------------
    def update(self, dt: float) -> None:
        now = time.time()
        try:
            self.backend.tick(now)
        except Exception:
            pass
        for ev in self.backend.poll():
            self._handle_backend_event(ev)

        if now - self._last_refresh > 3.0:
            self._load_feed()

        if self.keyboard.active and self.keyboard.title.startswith("Pesquisar"):
            if self.keyboard.text != self.search:
                self.search = self.keyboard.text
                self.search_active = bool(self.search)
                self._load_feed()

        if self.view == "pin":
            max_scroll = self._max_scroll()
            self.scroll = clamp(self.scroll, 0, max_scroll)

    def _handle_backend_event(self, ev) -> None:
        kind = ev.kind
        data = ev.data
        if kind in ("pins", "boards", "image"):
            self._load_feed()
        elif kind == "connected":
            self._load_feed()
            self._toast("Conectado!", "ok")
        elif kind == "error":
            self._toast(data.get("text", "Erro no backend."), "error")

    # -- layout -------------------------------------------------------------
    def _columns(self) -> int:
        w = self.logical_size[0]
        return max(2, min(5, w // 210))

    def _feed_viewport(self) -> pygame.Rect:
        w, h = self.logical_size
        top = self.HEADER_H + (self.SEARCH_H if (self.search_active or self.search) else 0)
        return pygame.Rect(0, top, w, h - top - self.HINT_H)

    def _feed_layout(self) -> tuple[list[tuple[pygame.Rect, Pin]], float]:
        viewport = self._feed_viewport()
        key = (self._feed_version, viewport.width, viewport.height, len(self.pins))
        if self._feed_layout_key == key and self._feed_layout_cache is not None:
            return self._feed_layout_cache

        cols = self._columns()
        gap = self.CARD_GAP
        margin = self.CARD_MARGIN
        card_w = (viewport.width - margin * 2 - gap * (cols - 1)) // cols
        card_w = max(80, card_w)
        col_y = [0] * cols
        cards: list[tuple[pygame.Rect, Pin]] = []

        for pin in self.pins:
            col = min(range(cols), key=lambda c: col_y[c])
            x = margin + col * (card_w + gap)
            aspect = pin.aspect if pin.aspect > 0.1 else 0.75
            thumb_h = int(card_w / aspect)
            thumb_h = int(clamp(thumb_h, int(card_w * 0.6), int(card_w * 1.9)))
            card_h = thumb_h + self.CAPTION_H
            rect = pygame.Rect(x, col_y[col], card_w, card_h)
            cards.append((rect, pin))
            col_y[col] += card_h + gap

        total = max(col_y) if col_y else 0
        self._feed_layout_key = key
        self._feed_layout_cache = (cards, float(total))
        return self._feed_layout_cache

    def _ensure_visible(self) -> None:
        cards, _total = self._feed_layout()
        if not (0 <= self.list_index < len(cards)):
            return
        rect, _ = cards[self.list_index]
        viewport = self._feed_viewport()
        if rect.y - self.scroll < 0:
            self.scroll = float(rect.y)
        elif rect.bottom - self.scroll > viewport.height:
            self.scroll = float(rect.bottom - viewport.height)
        max_scroll = self._max_feed_scroll()
        self.scroll = clamp(self.scroll, 0, max_scroll)

    def _max_feed_scroll(self) -> float:
        _cards, total = self._feed_layout()
        viewport = self._feed_viewport()
        return max(0.0, total - viewport.height)

    def _pin_viewport(self) -> pygame.Rect:
        w, h = self.logical_size
        return pygame.Rect(0, self.HEADER_H, w, h - self.HEADER_H - self.HINT_H)

    def _pin_layout(self) -> tuple[list, float]:
        viewport = self._pin_viewport()
        pin = self._selected_pin()
        key = (self.selected_pin_id, pin.image_path if pin else "", viewport.width, viewport.height)
        if self._pin_layout_key == key and self._pin_layout_cache is not None:
            return self._pin_layout_cache
        if not pin:
            self._pin_layout_key = key
            self._pin_layout_cache = ([], 0.0)
            return self._pin_layout_cache

        pad = 16
        max_text = viewport.width - pad * 2
        f_title = self.fonts.get(19, True)
        f_meta = self.fonts.get(12)
        f_text = self.fonts.get(14)

        items = []
        y = pad

        # imagem
        max_h = int(viewport.height * 0.48)
        img_w, img_h = self._detail_image_size(pin, viewport.width - pad * 2, max_h)
        img_rect = pygame.Rect(pad, y, img_w, img_h)
        items.append(("image", img_rect))
        y += img_h + 14

        # título
        title_lines = wrap_text(f_title, pin.display_title(), max_text, max_lines=3)
        title_h = len(title_lines) * (f_title.get_height() + 3)
        items.append(("title", title_lines, y, title_h))
        y += title_h + 6

        # meta
        board_title = ""
        for b in self.backend.boards():
            if b.id == pin.board_id:
                board_title = b.display_title()
                break
        meta_bits = [bit for bit in (pin.author, board_title, f"{pin.saves} salvos", format_time(pin.ts)) if bit]
        meta_line = " · ".join(meta_bits)
        meta_lines = wrap_text(f_meta, meta_line, max_text, max_lines=2)
        meta_h = len(meta_lines) * (f_meta.get_height() + 2)
        items.append(("meta", meta_lines, y, meta_h))
        y += meta_h + 10

        # descrição
        desc_lines = wrap_text(f_text, pin.description or "(sem descrição)", max_text, max_lines=30)
        desc_h = len(desc_lines) * (f_text.get_height() + 3)
        items.append(("desc", desc_lines, y, desc_h))
        y += desc_h + 12

        # link
        if pin.url:
            link_lines = wrap_text(f_meta, pin.url, max_text, max_lines=3)
            link_h = len(link_lines) * (f_meta.get_height() + 2)
            items.append(("link", link_lines, y, link_h))
            y += link_h + 8

        total = y + pad
        self._pin_layout_key = key
        self._pin_layout_cache = (items, total)
        return self._pin_layout_cache

    def _max_scroll(self) -> float:
        _items, total = self._pin_layout()
        viewport = self._pin_viewport()
        return max(0.0, total - viewport.height)

    # -- imagens ------------------------------------------------------------
    def _pin_thumb(self, pin: Pin, w: int, h: int) -> pygame.Surface:
        key = (pin.id, int(w), int(h))
        cached = self._thumb_cache.get(key)
        if cached is not None:
            return cached
        surf: Optional[pygame.Surface] = None
        if pin.image_path:
            try:
                raw = pygame.image.load(pin.image_path)
                surf = pygame.transform.smoothscale(raw, (max(8, int(w)), max(8, int(h))))
            except Exception:
                surf = None
        if surf is None:
            surf = make_thumb(pin, w, h)
        if len(self._thumb_cache) > 240:
            self._thumb_cache.clear()
        self._thumb_cache[key] = surf
        return surf

    def _detail_image_size(self, pin: Pin, max_w: int, max_h: int) -> tuple[int, int]:
        aspect = pin.aspect if pin.aspect > 0.1 else 0.75
        w = max_w
        h = int(w / aspect)
        if h > max_h:
            h = max_h
            w = int(h * aspect)
        return max(40, w), max(40, h)

    # -- desenho ------------------------------------------------------------
    def step(self, dt: float = 1 / 60) -> None:
        self.handle_events()
        self.update(dt)
        self.draw()
        self._present()

    def run(self) -> None:
        while self.running:
            dt = self._clock.tick(config.FPS) / 1000.0
            self.step(dt)
        self.shutdown()

    def shutdown(self) -> None:
        try:
            self.backend.stop()
        except Exception:
            pass
        try:
            self.store.close()
        except Exception:
            pass
        pygame.quit()

    def draw(self) -> None:
        now = time.time()
        self._hits = []
        self.surface.fill(config.BG)

        if self.view == "feed":
            self._draw_feed()
        elif self.view == "pin":
            self._draw_pin()
        elif self.view == "boards":
            self._draw_boards()

        if self.modal:
            self._draw_modal(now)
        self.keyboard.draw(self.surface, now)
        if self.toast:
            draw_toast(self.surface, self.toast, self.fonts.get(13), now)
            if not self.toast.alive(now):
                self.toast = None

    def _draw_header(
        self,
        title: str,
        back_action: Optional[str] = None,
        buttons: tuple[str, ...] = ("search", "boards", "refresh", "settings"),
    ) -> None:
        w, _h = self.logical_size
        pygame.draw.rect(self.surface, config.HEADER, pygame.Rect(0, 0, w, self.HEADER_H))
        pygame.draw.rect(self.surface, config.DIVIDER, pygame.Rect(0, self.HEADER_H - 1, w, 1))

        x = 12
        if back_action:
            self._icon_button(pygame.Rect(x, 10, 36, 36), "back", back_action)
            x += 44
        else:
            # logo "P"
            logo = pygame.Rect(x, 10, 36, 36)
            draw_round_rect(self.surface, config.ACCENT, logo, radius=18)
            draw_text(self.surface, "P", logo.center, self.fonts.get(20, True), config.WHITE, anchor="center")
            x += 44

        f_title = self.fonts.get(19, True)
        draw_text(self.surface, truncate(f_title, title, w - x - 44 * len(buttons) - 40), (x, 16), f_title, config.TEXT)

        bx = w - 12 - 36
        for icon in reversed(buttons):
            self._icon_button(pygame.Rect(bx, 10, 36, 36), icon, icon)
            bx -= 44

    def _draw_feed(self) -> None:
        w, h = self.logical_size

        # título do header
        if self.saved_only:
            title = "Meus salvos"
        elif self.board_filter:
            title = next((b.display_title() for b in self.backend.boards() if b.id == self.board_filter), "Pinterest")
        else:
            title = "Pinterest"
        self._draw_header(title, back_action="clear_filter" if (self.board_filter or self.saved_only or self.search) else None)

        # barra de busca
        top = self.HEADER_H
        if self.search_active or self.search:
            field = pygame.Rect(12, top + 6, w - 24, self.SEARCH_H - 12)
            draw_round_rect(self.surface, config.PANEL_2, field, radius=18)
            pygame.draw.rect(self.surface, config.ACCENT, field, width=1, border_radius=18)
            f = self.fonts.get(14)
            draw_text(
                self.surface,
                truncate(f, self.search or "Pesquisar...", field.width - 70),
                (field.x + 14, field.y + 6),
                f,
                config.TEXT if self.search else config.TEXT_DIM,
            )
            self._icon_button(pygame.Rect(field.right - 30, field.y + 3, 24, 24), "close", "clear_search")
            top += self.SEARCH_H

        viewport = pygame.Rect(0, top, w, h - top - self.HINT_H)

        if not self.pins:
            f = self.fonts.get(14)
            msg = "Nenhum pin encontrado." if (self.search or self.board_filter or self.saved_only) else "Nenhum pin ainda."
            draw_text(self.surface, msg, (viewport.centerx, viewport.y + 70), f, config.TEXT_DIM, anchor="midtop")
            sub = "Configure a API ou volte ao modo demo." if self.backend_kind == "api" else "Sincronize ou limpe os filtros."
            draw_text(self.surface, sub, (viewport.centerx, viewport.y + 96), self.fonts.get(12), config.TEXT_FAINT, anchor="midtop")
            self._draw_hint_bar()
            return

        cards, total = self._feed_layout()
        f_title = self.fonts.get(13, True)
        f_sub = self.fonts.get(11)
        selected_rect: Optional[pygame.Rect] = None

        for idx, (rect, pin) in enumerate(cards):
            y = viewport.y + rect.y - self.scroll
            if y + rect.height < viewport.y or y > viewport.bottom:
                continue
            card = pygame.Rect(rect.x, y, rect.width, rect.height)

            # fundo do card
            draw_round_rect(self.surface, config.BG_CARD, card, radius=10)

            # miniatura
            thumb = pygame.Rect(card.x, card.y, card.width, card.height - self.CAPTION_H)
            img = self._pin_thumb(pin, thumb.width, thumb.height)
            self.surface.blit(img, thumb)

            # salvo: badge (desenhado, sem glifos)
            if pin.is_saved:
                badge = pygame.Rect(thumb.right - 26, thumb.y + 6, 20, 20)
                draw_round_rect(self.surface, config.ACCENT, badge, radius=10)
                pygame.draw.line(self.surface, config.WHITE, (badge.x + 5, badge.y + 10), (badge.x + 9, badge.y + 14), 2)
                pygame.draw.line(self.surface, config.WHITE, (badge.x + 9, badge.y + 14), (badge.x + 15, badge.y + 6), 2)

            # legenda
            cy = thumb.bottom + 5
            draw_text(
                self.surface,
                truncate(f_title, pin.display_title(), card.width - 14),
                (card.x + 7, cy),
                f_title,
                config.TEXT,
            )
            draw_text(
                self.surface,
                truncate(f_sub, pin.author or "Pinterest", card.width - 14),
                (card.x + 7, cy + 18),
                f_sub,
                config.TEXT_DIM,
            )

            if idx == self.list_index:
                selected_rect = pygame.Rect(card)
            self._add_hit(card, f"pin:{pin.id}")

        if selected_rect is not None:
            pygame.draw.rect(self.surface, config.ACCENT, selected_rect, width=3, border_radius=10)

        # scrollbar
        if total > viewport.height:
            vis = viewport.height / total
            offset = self.scroll / max(1.0, self._max_feed_scroll())
            draw_scrollbar(self.surface, pygame.Rect(w - 5, viewport.y + 4, 3, viewport.height - 8), vis, offset)

        self._draw_hint_bar()

    def _draw_pin(self) -> None:
        pin = self._selected_pin()
        if not pin:
            self.view = "feed"
            return
        w, _h = self.logical_size
        self._draw_header("Pin", back_action="back", buttons=())

        # botão salvar no header
        save_rect = pygame.Rect(w - 56, 10, 44, 36)
        draw_round_rect(self.surface, config.ACCENT if pin.is_saved else config.PANEL_2, save_rect, radius=9)
        star = star_points(save_rect.centerx, save_rect.centery, 11, 4.5)
        if pin.is_saved:
            pygame.draw.polygon(self.surface, config.WHITE, star)
        else:
            pygame.draw.polygon(self.surface, config.TEXT_DIM, star, 2)
        self._add_hit(save_rect, "save")

        viewport = self._pin_viewport()
        pygame.draw.rect(self.surface, config.BG, viewport)
        items, total = self._pin_layout()
        # conteúdo alinhado ao topo; scroll desloca para cima
        content_top = viewport.y - self.scroll

        f_title = self.fonts.get(19, True)
        f_meta = self.fonts.get(12)
        f_text = self.fonts.get(14)

        for item in items:
            kind = item[0]
            if kind == "image":
                rect: pygame.Rect = item[1]
                y = content_top + rect.y
                if y + rect.height < viewport.y or y > viewport.bottom:
                    continue
                img = self._pin_thumb(pin, rect.width, rect.height)
                self.surface.blit(img, (rect.x, y))
            elif kind in ("title", "meta", "desc", "link"):
                _kind, lines, ty, th = item
                y = content_top + ty
                if y + th < viewport.y or y > viewport.bottom:
                    continue
                font = f_title if kind == "title" else (f_text if kind == "desc" else f_meta)
                color = config.TEXT if kind in ("title", "desc") else (
                    config.ACCENT if kind == "link" else config.TEXT_DIM
                )
                line_y = y
                for line in lines:
                    draw_text(self.surface, line, (16, line_y), font, color)
                    line_y += font.get_height() + (3 if kind in ("title", "desc") else 2)

        if total > viewport.height:
            vis = viewport.height / total
            max_scroll = self._max_scroll()
            offset = self.scroll / max(1.0, max_scroll) if max_scroll > 0 else 1.0
            draw_scrollbar(self.surface, pygame.Rect(w - 6, viewport.y + 6, 4, viewport.height - 12), vis, offset)

        self._draw_hint_bar()

    def _draw_boards(self) -> None:
        w, h = self.logical_size
        self._draw_header("Boards", back_action="back")
        viewport = pygame.Rect(0, self.HEADER_H, w, h - self.HEADER_H - self.HINT_H)
        pygame.draw.rect(self.surface, config.BG, viewport)

        boards = self.backend.boards()
        if not boards:
            draw_text(
                self.surface,
                "Nenhum board ainda.",
                (viewport.centerx, viewport.y + 70),
                self.fonts.get(14),
                config.TEXT_DIM,
                anchor="midtop",
            )
            self._draw_hint_bar()
            return

        from ..models import board_color

        f_title = self.fonts.get(15, True)
        f_sub = self.fonts.get(12)
        y = viewport.y + 8
        row_h = 56
        for idx, board in enumerate(boards):
            if y > viewport.bottom:
                break
            rect = pygame.Rect(10, y, w - 24, row_h - 6)
            focused = idx == self._boards_index
            if focused:
                draw_round_rect(self.surface, config.SELECT, rect, radius=10)
                pygame.draw.rect(self.surface, config.ACCENT, pygame.Rect(rect.x, rect.y + 6, 3, rect.height - 12), border_radius=2)

            tile = pygame.Rect(rect.x + 8, rect.y + 6, 36, 36)
            draw_round_rect(self.surface, board_color(board.id), tile, radius=8)
            draw_text(self.surface, (board.display_title()[:1] or "B").upper(), tile.center, self.fonts.get(16, True), config.WHITE, anchor="center")

            draw_text(
                self.surface,
                truncate(f_title, board.display_title(), rect.width - 90),
                (rect.x + 54, rect.y + 8),
                f_title,
                config.TEXT,
            )
            count = board.pin_count or self.store.count_pins(board.id)
            draw_text(
                self.surface,
                truncate(f_sub, f"{count} pins", rect.width - 90),
                (rect.x + 54, rect.y + 28),
                f_sub,
                config.TEXT_DIM,
            )
            self._add_hit(rect, f"board:{board.id}")
            y += row_h

        self._draw_hint_bar()

    def _draw_hint_bar(self) -> None:
        w, h = self.logical_size
        bar = pygame.Rect(0, h - self.HINT_H, w, self.HINT_H)
        pygame.draw.rect(self.surface, config.HEADER_2, bar)
        pygame.draw.rect(self.surface, config.DIVIDER, pygame.Rect(0, bar.y, w, 1))
        if self.view == "feed":
            hint = "Setas: navegar · A: abrir · X: buscar · Y: boards · Start: config"
        elif self.view == "pin":
            hint = "A/Espaço: salvar · B: voltar · Start: config"
        else:
            hint = "A: abrir board · B: voltar"
        f = self.fonts.get(11)
        draw_text(self.surface, truncate(f, hint, w - 24), (w // 2, bar.y + 6), f, config.TEXT_DIM, anchor="midtop")

    # -- modais -------------------------------------------------------------
    def _draw_modal(self, now: float) -> None:
        dim = pygame.Surface(self.logical_size, pygame.SRCALPHA)
        dim.fill((0, 0, 0, 165))
        self.surface.blit(dim, (0, 0))
        if self.modal == "settings":
            self._draw_settings()
        elif self.modal == "about":
            self._draw_about()

    def _panel(self, w: int, h: int) -> pygame.Rect:
        sw, sh = self.logical_size
        rect = pygame.Rect(0, 0, min(w, sw - 24), min(h, sh - 24))
        rect.center = (sw // 2, sh // 2)
        draw_round_rect(self.surface, config.PANEL, rect, radius=14)
        pygame.draw.rect(self.surface, config.DIVIDER, rect, width=1, border_radius=14)
        return rect

    def _draw_settings(self) -> None:
        panel = self._panel(640, 500)
        draw_text(self.surface, "Configurações", (panel.x + 22, panel.y + 16), self.fonts.get(19, True), config.TEXT)
        draw_text(self.surface, config.APP_VERSION, (panel.right - 22, panel.y + 20), self.fonts.get(11), config.TEXT_FAINT, anchor="topright")
        rows = self._settings_rows()
        y = panel.y + 58
        f = self.fonts.get(13)
        fv = self.fonts.get(12)
        for i, row in enumerate(rows):
            r = pygame.Rect(panel.x + 14, y, panel.width - 28, 32)
            if i == self._settings_index:
                draw_round_rect(self.surface, config.SELECT, r, radius=7)
                pygame.draw.rect(self.surface, config.ACCENT, pygame.Rect(r.x, r.y + 6, 3, r.height - 12), border_radius=2)
            draw_text(self.surface, row["label"], (r.x + 14, r.y + 7), f, config.TEXT)
            if row.get("value"):
                draw_text(self.surface, truncate(fv, row["value"], r.width - 220), (r.right - 12, r.y + 8), fv, config.TEXT_DIM, anchor="topright")
            self._add_hit(r, f"settings_row:{i}")
            y += 34
        stats = self.store.stats()
        footer_y = panel.bottom - 46
        pygame.draw.rect(self.surface, config.DIVIDER, pygame.Rect(panel.x + 14, footer_y - 8, panel.width - 28, 1))
        draw_text(
            self.surface,
            f"Pins: {stats['pins']} · Boards: {stats['boards']} · Salvos: {stats['saved']}",
            (panel.x + 22, footer_y),
            self.fonts.get(10),
            config.TEXT_FAINT,
        )
        draw_text(
            self.surface,
            "Setas: navegar · Enter: ativar · Esc: fechar",
            (panel.right - 22, footer_y),
            self.fonts.get(10),
            config.TEXT_FAINT,
            anchor="topright",
        )

    def _draw_about(self) -> None:
        panel = self._panel(620, 420)
        draw_text(self.surface, "Sobre", (panel.x + 22, panel.y + 16), self.fonts.get(19, True), config.TEXT)
        f = self.fonts.get(13)
        f_small = self.fonts.get(11)
        y = panel.y + 58
        paragraphs = [
            ("O que é", True),
            ("Pinterest do OddHub: feed de pins em grade masonry para PortMaster.", False),
            ("Funcionalidades", True),
            ("Modo demo offline com pins de exemplo, API real (v5) com token, busca, boards e salvos.", False),
            ("Limites", True),
            ("A API real requer token PINTEREST_TOKEN. Sem login social no dispositivo.", False),
            ("Dados", True),
            (f"Pins e cache de imagens ficam em: {self.data_dir}", False),
        ]
        for text, header in paragraphs:
            if header:
                draw_text(self.surface, text, (panel.x + 24, y), self.fonts.get(12, True), config.ACCENT)
                y += 22
            else:
                for line in wrap_text(f_small, text, panel.width - 48, max_lines=5):
                    draw_text(self.surface, line, (panel.x + 24, y), f_small, config.TEXT_DIM)
                    y += f_small.get_height() + 2
                y += 6
        close = pygame.Rect(panel.right - 130, panel.bottom - 54, 106, 36)
        draw_round_rect(self.surface, config.PANEL_2, close, radius=9)
        draw_text(self.surface, "Fechar", close.center, f, config.TEXT, anchor="center")
        self._add_hit(close, "about_close")

    # -- helpers ------------------------------------------------------------
    def _add_hit(self, rect: pygame.Rect, action: str) -> None:
        self._hits.append((pygame.Rect(rect), action))

    def _hit(self, pos: tuple[int, int]) -> Optional[str]:
        for rect, action in reversed(self._hits):
            if rect.collidepoint(pos):
                return action
        return None

    def _icon_button(self, rect: pygame.Rect, icon: str, action: str) -> None:
        hover = rect.collidepoint(self._mouse_pos)
        if hover:
            draw_round_rect(self.surface, config.SELECT, rect, radius=8)
        c = config.TEXT if hover else config.TEXT_DIM
        cx, cy = rect.center
        if icon == "search":
            pygame.draw.circle(self.surface, c, (cx - 2, cy - 2), 7, 2)
            pygame.draw.line(self.surface, c, (cx + 3, cy + 3), (cx + 9, cy + 9), 2)
        elif icon == "refresh":
            pygame.draw.arc(self.surface, c, pygame.Rect(cx - 8, cy - 8, 16, 16), 0.4, 5.6, 2)
            pygame.draw.line(self.surface, c, (cx + 4, cy - 9), (cx + 9, cy - 4), 2)
        elif icon == "settings":
            for i, dy in enumerate((-7, 0, 7)):
                pygame.draw.line(self.surface, c, (cx - 9, cy + dy), (cx + 9, cy + dy), 2)
                pygame.draw.circle(self.surface, c, (cx + (-4 if i != 1 else 5), cy + dy), 3)
        elif icon == "back":
            pygame.draw.line(self.surface, c, (cx + 6, cy - 8), (cx - 4, cy), 2)
            pygame.draw.line(self.surface, c, (cx - 4, cy), (cx + 6, cy + 8), 2)
        elif icon == "boards":
            for dx in (-5, 5):
                for dy in (-5, 5):
                    pygame.draw.rect(self.surface, c, pygame.Rect(cx + dx - 3, cy + dy - 3, 6, 6), 1)
        elif icon == "close":
            pygame.draw.line(self.surface, c, (cx - 5, cy - 5), (cx + 5, cy + 5), 2)
            pygame.draw.line(self.surface, c, (cx + 5, cy - 5), (cx - 5, cy + 5), 2)
        self._add_hit(rect, action)
