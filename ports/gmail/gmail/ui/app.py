"""Aplicativo pygame do port Gmail/PortMail."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import pygame

from .. import config
from ..backend import make_backend
from ..models import Email, format_time, format_full_time, preview_text
from ..store import Store
from .keyboard import OnScreenKeyboard
from .widgets import (
    FontBook,
    Toast,
    clamp,
    draw_avatar,
    draw_badge,
    draw_round_rect,
    draw_scrollbar,
    draw_text,
    draw_toast,
    truncate,
    wrap_text,
)


class App:
    HEADER_H = 64
    LIST_H = 72
    COMPOSE_H = 58

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

        self.store = Store(self.data_dir / "emails.sqlite3")
        saved = self.store.meta_get("backend", "demo")
        self.backend_kind = (backend_kind or saved or "demo").lower()
        if self.backend_kind not in ("demo", "imap"):
            self.backend_kind = "demo"
        self.backend = make_backend(self.backend_kind, self.store, self.data_dir)
        self.backend.start()

        self.keyboard = OnScreenKeyboard(self.fonts)
        self.running = True
        self.view = "emails"                    # emails | email | compose
        self.modal: Optional[str] = None        # settings | accounts | compose | about
        self.selected_email_id: Optional[str] = None
        self.list_index = 0
        self.emails: list[Email] = []
        self.scroll = 0.0
        self.compose_to = ""
        self.compose_subject = ""
        self.compose_body = ""
        self.search = ""
        self.search_active = False
        self.toast: Optional[Toast] = None
        self._hits: list[tuple[pygame.Rect, str]] = []
        self._email_layout_cache = None
        self._email_layout_key = None
        self._last_refresh = 0.0
        self._scroll_to_bottom = True
        self._settings_index = 0
        self._compose_index = 0
        self._mouse_pos = (0, 0)
        self._clock = pygame.time.Clock()
        self._joy = None
        self._joy_axis = (0, 0)
        self._joy_repeat_at = 0.0

        self._init_joystick()
        self._refresh_emails()
        if self.backend_kind == "imap":
            self.modal = "accounts"
        pygame.display.set_caption(f"{config.APP_NAME} — OddHub")

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

    def _refresh_emails(self) -> None:
        account = self.backend.default_account()
        if account:
            self.emails = self.backend.emails(account.id, "INBOX", 200)
            if self.search.strip():
                q = self.search.strip().lower()
                self.emails = [
                    e for e in self.emails
                    if q in e.subject.lower() or q in e.sender.lower() or q in e.body_text.lower()
                ]
        if self.list_index >= len(self.emails):
            self.list_index = max(0, len(self.emails) - 1)
        if self.selected_email_id and not any(e.id == self.selected_email_id for e in self.emails):
            self.selected_email_id = None
        self._last_refresh = time.time()

    def _selected_email(self) -> Optional[Email]:
        if not self.selected_email_id:
            return None
        for email in self.emails:
            if email.id == self.selected_email_id:
                return email
        return None

    def _open_email(self, email_id: str) -> None:
        self.selected_email_id = email_id
        email = self.backend.email(email_id)
        if email and not email.is_read:
            self.backend.mark_read(email_id, True)
            email.is_read = True
        self.view = "email"
        self._scroll_to_bottom = True

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
            self._refresh_emails()
            return
        if self.view == "email":
            self.view = "emails"
            return
        if self.view == "compose":
            self.view = "emails"
            return
        self.running = False

    def _open_compose(self) -> None:
        self.view = "compose"
        self.compose_to = ""
        self.compose_subject = ""
        self.compose_body = ""
        self._compose_index = 0
        self.keyboard.open("Para:", "", self._set_compose_to, max_len=500)

    def _set_compose_to(self, text: str) -> None:
        self.compose_to = text.strip()
        if self.compose_to:
            self.keyboard.open("Assunto:", "", self._set_compose_subject, max_len=200)

    def _set_compose_subject(self, text: str) -> None:
        self.compose_subject = text.strip()
        if self.compose_subject:
            self.keyboard.open("Mensagem:", "", self._set_compose_body, max_len=10000)

    def _set_compose_body(self, text: str) -> None:
        self.compose_body = text

    def _send_compose(self) -> None:
        if not self.compose_to or not self.compose_body:
            self._toast("Preencha destinatário e mensagem.", "warn")
            return
        to = [r.strip() for r in self.compose_to.split(",") if r.strip()]
        email = self.backend.send_email(to, self.compose_subject, self.compose_body)
        if email:
            self._toast("Email enviado!", "ok")
            self.view = "emails"
            self._refresh_emails()
        else:
            self._toast("Falha ao enviar.", "error")

    def _toast(self, text: str, kind: str = "info") -> None:
        self.toast = Toast(text, kind)

    def _open_settings(self) -> None:
        self.modal = "settings"
        self._settings_index = 0

    def _settings_rows(self) -> list[dict]:
        rows = [
            {"label": "Backend", "value": self.backend.label, "action": "toggle_backend"},
            {"label": "Status", "value": self.backend.status_label(), "action": "none"},
            {"label": "Contas", "value": f"{len(self.backend.accounts())} configurada(s)", "action": "accounts"},
            {"label": "Emails", "value": f"{len(self.emails)} no total", "action": "none"},
            {"label": "Atualizar", "value": "Sincronizar agora", "action": "refresh"},
            {"label": "Buscar", "value": "Pesquisar emails", "action": "search"},
            {"label": "Sobre", "value": "Informações do port", "action": "about"},
            {"label": "Fechar", "value": "", "action": "close"},
        ]
        return rows

    def _activate_setting(self, action: str) -> None:
        if action in ("none", ""):
            return
        if action == "toggle_backend":
            self._toggle_backend()
        elif action == "accounts":
            self.modal = "accounts"
        elif action == "refresh":
            self.backend.refresh()
            self._refresh_emails()
            self._toast("Sincronizando...", "info")
        elif action == "search":
            self.search_active = True
            self.keyboard.open("Pesquisar", self.search, self._set_search, max_len=100)
        elif action == "about":
            self.modal = "about"
        elif action == "close":
            self.modal = None

    def _set_search(self, text: str) -> None:
        self.search = text.strip()
        self.search_active = bool(self.search)
        self._refresh_emails()

    def _toggle_backend(self) -> None:
        kind = "imap" if self.backend_kind == "demo" else "demo"
        try:
            self.backend.stop()
        except Exception:
            pass
        self.backend_kind = kind
        self.store.meta_set("backend", kind)
        self.backend = make_backend(kind, self.store, self.data_dir)
        self.backend.start()
        self.selected_email_id = None
        self._refresh_emails()
        if kind == "imap":
            self.modal = "accounts"
            self._toast("Backend real iniciado. Configure sua conta.", "info")
        else:
            self.modal = None
            self._toast("Modo demo ativado.", "ok")

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

    def _handle_key(self, event: pygame.event.Event) -> None:
        key = event.key
        if key in (pygame.K_UP, pygame.K_KP8):
            if self.view == "emails" and self.emails:
                self.list_index = (self.list_index - 1) % len(self.emails)
            elif self.view == "email":
                self.scroll += 70
        elif key in (pygame.K_DOWN, pygame.K_KP2):
            if self.view == "emails" and self.emails:
                self.list_index = (self.list_index + 1) % len(self.emails)
            elif self.view == "email":
                self.scroll -= 70
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.view == "emails":
                if self.emails:
                    self._open_email(self.emails[self.list_index].id)
            elif self.view == "compose":
                self._send_compose()
        elif key in (pygame.K_BACKSPACE, pygame.K_DELETE):
            if self.view == "email":
                self._back()
            else:
                self._back()
        elif key == pygame.K_ESCAPE:
            self._back()
        elif key == pygame.K_F1:
            self.modal = "about"
        elif event.unicode and event.unicode.isprintable():
            if self.view == "compose":
                # No compose, digitar adiciona ao corpo
                if self.compose_body:
                    self.compose_body += event.unicode
                else:
                    self.compose_body = event.unicode
            else:
                self.search_active = True
                self.search += event.unicode
                self._refresh_emails()

    def _handle_mouse(self, event: pygame.event.Event) -> None:
        pos = event.pos
        if event.button == 4:
            if self.view == "emails" and self.emails:
                self.list_index = max(0, self.list_index - 1)
            elif self.view == "email":
                self.scroll += 90
            return
        if event.button == 5:
            if self.view == "emails" and self.emails:
                self.list_index = min(len(self.emails) - 1, self.list_index + 1)
            elif self.view == "email":
                self.scroll -= 90
            return
        if event.button != 1:
            return
        action = self._hit(pos)
        if not action:
            return
        if action.startswith("row:"):
            self._open_email(action.split(":", 1)[1])
        elif action.startswith("settings_row:"):
            idx = int(action.split(":", 1)[1])
            rows = self._settings_rows()
            if 0 <= idx < len(rows):
                self._activate_setting(rows[idx]["action"])
        elif action == "compose":
            self._open_compose()
        elif action == "settings":
            self._open_settings()
        elif action == "search":
            self.search_active = True
            self.keyboard.open("Pesquisar", self.search, self._set_search, max_len=100)
        elif action == "clear_search":
            self.search = ""
            self.search_active = False
            self._refresh_emails()
        elif action == "back":
            self._back()
        elif action == "send":
            self._send_compose()
        elif action == "refresh":
            self.backend.refresh()
            self._refresh_emails()
            self._toast("Sincronizando...", "info")
        elif action == "star":
            if self.selected_email_id:
                self.backend.toggle_star(self.selected_email_id)
                self._refresh_emails()
        elif action == "important":
            if self.selected_email_id:
                self.backend.toggle_important(self.selected_email_id)
                self._refresh_emails()
        elif action == "delete":
            if self.selected_email_id:
                self.backend.delete_email(self.selected_email_id)
                self._back()
                self._refresh_emails()
                self._toast("Email excluído.", "ok")
        elif action in ("settings_close", "about_close"):
            self.modal = None
        elif action == "compose_to_field":
            self.keyboard.open("Para:", self.compose_to, self._set_compose_to, max_len=500)
        elif action == "compose_subject_field":
            self.keyboard.open("Assunto:", self.compose_subject, self._set_compose_subject, max_len=200)
        elif action == "compose_body_field":
            self.keyboard.open("Mensagem:", self.compose_body, self._set_compose_body, max_len=10000)

    def _handle_wheel(self, event: pygame.event.Event) -> None:
        if self.modal:
            return
        if self.view == "emails" and self.emails:
            self.list_index = int(clamp(self.list_index - event.y, 0, len(self.emails) - 1))
        elif self.view == "email":
            self.scroll += event.y * 60

    def _handle_joy(self, event: pygame.event.Event) -> None:
        if event.type == pygame.JOYBUTTONDOWN:
            button = event.button
            if button in (0,):  # A
                if self.view == "emails":
                    if self.emails:
                        self._open_email(self.emails[self.list_index].id)
                elif self.view == "compose":
                    self._send_compose()
            elif button in (1,):  # B
                self._back()
            elif button in (2,):  # X
                if self.view == "emails":
                    self._open_compose()
            elif button in (3,):  # Y
                self.search_active = True
                self.keyboard.open("Pesquisar", self.search, self._set_search, max_len=100)
            elif button in (6, 7):  # Select/Start
                self._open_settings()
        elif event.type == pygame.JOYHATMOTION:
            x, y = event.value
            if y == 1:
                if self.view == "emails" and self.emails:
                    self.list_index = (self.list_index - 1) % len(self.emails)
                elif self.view == "email":
                    self.scroll += 70
            elif y == -1:
                if self.view == "emails" and self.emails:
                    self.list_index = (self.list_index + 1) % len(self.emails)
                elif self.view == "email":
                    self.scroll -= 70
        elif event.type == pygame.JOYAXISMOTION:
            ax = event.axis
            val = event.value
            if ax == 1:
                old = self._joy_axis[1]
                new = 1 if val > 0.55 else (-1 if val < -0.55 else 0)
                if new != old:
                    self._joy_axis = (self._joy_axis[0], new)
                    if new == -1:
                        if self.view == "emails" and self.emails:
                            self.list_index = (self.list_index + 1) % len(self.emails)
                        elif self.view == "email":
                            self.scroll -= 70
                    elif new == 1:
                        if self.view == "emails" and self.emails:
                            self.list_index = (self.list_index - 1) % len(self.emails)
                        elif self.view == "email":
                            self.scroll += 70

    def _handle_modal_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.modal = None
            return True
        if self.modal == "settings":
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_KP8):
                    self._settings_index = max(0, self._settings_index - 1)
                    return True
                if event.key in (pygame.K_DOWN, pygame.K_KP2):
                    self._settings_index = min(len(self._settings_rows()) - 1, self._settings_index + 1)
                    return True
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._activate_setting(self._settings_rows()[self._settings_index]["action"])
                    return True
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self._toggle_backend()
                    return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action = self._hit(event.pos)
                if action and action.startswith("settings_row:"):
                    self._settings_index = int(action.split(":", 1)[1])
                    self._activate_setting(self._settings_rows()[self._settings_index]["action"])
                    return True
        elif self.modal == "accounts":
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                self.modal = None
                return True
        elif self.modal == "about":
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.modal = None
                return True
        return False

    def update(self, dt: float) -> None:
        now = time.time()
        try:
            self.backend.tick(now)
        except Exception:
            pass
        for ev in self.backend.poll():
            self._handle_backend_event(ev)

        if now - self._last_refresh > 2.0:
            self._refresh_emails()

        if self.keyboard.active and self.keyboard.title == "Pesquisar":
            if self.keyboard.text != self.search:
                self.search = self.keyboard.text
                self.search_active = bool(self.search)
                self._refresh_emails()

        if self._scroll_to_bottom:
            self.scroll = 0.0
            self._scroll_to_bottom = False

        if self.view == "email":
            max_scroll = self._max_scroll()
            self.scroll = clamp(self.scroll, 0, max_scroll)

    def _handle_backend_event(self, ev) -> None:
        kind = ev.kind
        data = ev.data
        if kind == "email":
            email: Optional[Email] = data.get("email")
            if email:
                self._refresh_emails()
        elif kind == "connected":
            self._refresh_emails()
            self._toast("Conectado!", "ok")
        elif kind == "status":
            pass
        elif kind == "error":
            self._toast(data.get("text", "Erro no backend."), "error")
        elif kind == "emails":
            self._refresh_emails()

    def _max_scroll(self) -> float:
        layout = self._email_layout()
        if not layout:
            return 0.0
        _, total = layout
        viewport = self._email_viewport()
        return max(0.0, total - viewport.height)

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

    def _list_viewport(self) -> pygame.Rect:
        w, h = self.logical_size
        return pygame.Rect(0, self.HEADER_H, w, h - self.HEADER_H - self.COMPOSE_H)

    def _email_viewport(self) -> pygame.Rect:
        w, h = self.logical_size
        return pygame.Rect(0, self.HEADER_H, w, h - self.HEADER_H - self.COMPOSE_H)

    def _email_layout(self):
        viewport = self._email_viewport()
        key = (self.selected_email_id, len(self.emails), viewport.width)
        if self._email_layout_key == key and self._email_layout_cache is not None:
            return self._email_layout_cache
        email = self._selected_email()
        if not email:
            self._email_layout_key = key
            self._email_layout_cache = ([], 0)
            return self._email_layout_cache

        f_text = self.fonts.get(15)
        f_name = self.fonts.get(14, True)
        f_meta = self.fonts.get(12)
        line_h = f_text.get_height() + 2
        pad_x = 16
        pad_y = 12
        max_text = viewport.width - pad_x * 2

        items = []
        total = 16
        # Cabeçalho do email
        items.append(("header", email, total, 80))
        total += 80
        # Corpo
        lines = wrap_text(f_text, email.body_text, max_text)
        body_h = len(lines) * line_h + pad_y * 2
        items.append(("body", email, total, body_h, lines))
        total += body_h + 8

        self._email_layout_key = key
        self._email_layout_cache = (items, total)
        return self._email_layout_cache

    def draw(self) -> None:
        now = time.time()
        self._hits = []
        self.surface.fill(config.BG)

        if self.view == "emails":
            self._draw_email_list()
        elif self.view == "email":
            self._draw_email_detail()
        elif self.view == "compose":
            self._draw_compose()

        if self.modal:
            self._draw_modal(now)
        self.keyboard.draw(self.surface, now)
        if self.toast:
            draw_toast(self.surface, self.toast, self.fonts.get(13), now)
            if not self.toast.alive(now):
                self.toast = None

    def _draw_email_list(self) -> None:
        w, h = self.logical_size
        # Header
        pygame.draw.rect(self.surface, config.HEADER, pygame.Rect(0, 0, w, self.HEADER_H))
        f_title = self.fonts.get(21, True)
        draw_text(self.surface, "PortMail", (16, 12), f_title, config.TEXT)
        
        # Botões do header
        self._icon_button(pygame.Rect(w - 136, 12, 36, 36), "refresh", "refresh")
        self._icon_button(pygame.Rect(w - 92, 12, 36, 36), "search", "search")
        self._icon_button(pygame.Rect(w - 48, 12, 36, 36), "settings", "settings")
        
        # Search bar
        if self.search_active:
            field = pygame.Rect(12, self.HEADER_H + 7, w - 24, 40)
            draw_round_rect(self.surface, config.PANEL_2, field, radius=18)
            pygame.draw.rect(self.surface, config.ACCENT, field, width=1, border_radius=18)
            f = self.fonts.get(14)
            draw_text(self.surface, truncate(f, self.search or "Pesquisar...", field.width - 70), (field.x + 14, field.y + 8), f, config.TEXT)
            self._icon_button(pygame.Rect(field.right - 30, field.y + 4, 24, 24), "close", "clear_search")
            list_y = self.HEADER_H + 54
        else:
            list_y = self.HEADER_H

        # Email list
        viewport = pygame.Rect(0, list_y, w, h - list_y - self.COMPOSE_H)
        pygame.draw.rect(self.surface, config.BG, viewport)
        
        if not self.emails:
            f = self.fonts.get(14)
            draw_text(self.surface, "Nenhum email.", (viewport.centerx, viewport.y + 60), f, config.TEXT_DIM, anchor="midtop")
            draw_text(self.surface, "Configure uma conta ou clique em Compor.", (viewport.centerx, viewport.y + 84), self.fonts.get(12), config.TEXT_FAINT, anchor="midtop")
            return

        f_sender = self.fonts.get(15, True)
        f_subject = self.fonts.get(14)
        f_preview = self.fonts.get(12)
        f_time = self.fonts.get(11)
        row_h = 72
        y = viewport.y
        
        for idx, email in enumerate(self.emails):
            if y > viewport.bottom:
                break
            rect = pygame.Rect(0, y, w, row_h)
            focused = idx == self.list_index
            if focused:
                pygame.draw.rect(self.surface, config.SELECT, rect)
                pygame.draw.rect(self.surface, config.ACCENT, pygame.Rect(0, y, 3, row_h))
            
            # Avatar
            draw_avatar(self.surface, (40, y + row_h // 2), 22, email.display_sender(), self.fonts.get(12, True))
            
            # Sender
            sender_w = w - 160
            draw_text(self.surface, truncate(f_sender, email.display_sender(), sender_w), (76, y + 10), f_sender, config.TEXT if not email.is_read else config.TEXT_DIM)
            
            # Time
            if email.ts:
                draw_text(self.surface, format_time(email.ts), (w - 14, y + 12), f_time, config.ACCENT if not email.is_read else config.TEXT_DIM, anchor="topright")
            
            # Subject
            draw_text(self.surface, truncate(f_subject, email.display_subject(), sender_w), (76, y + 30), f_subject, config.TEXT if not email.is_read else config.TEXT_DIM)
            
            # Preview
            preview = preview_text(email.body_text or email.snippet, 80)
            draw_text(self.surface, truncate(f_preview, preview, sender_w), (76, y + 50), f_preview, config.TEXT_DIM)
            
            # Unread badge
            if not email.is_read:
                pygame.draw.circle(self.surface, config.UNREAD, (w - 14, y + row_h // 2), 4)
            
            # Divider
            pygame.draw.rect(self.surface, config.DIVIDER, pygame.Rect(76, rect.bottom - 1, w - 76, 1))
            self._add_hit(rect, f"row:{email.id}")
            y += row_h

        # Scrollbar
        if len(self.emails) * row_h > viewport.height:
            vis = viewport.height / (len(self.emails) * row_h)
            draw_scrollbar(self.surface, pygame.Rect(w - 5, viewport.y + 4, 3, viewport.height - 8), vis, self.list_index / max(1, len(self.emails) - 1))

        # Compose button
        compose_btn = pygame.Rect(w - 64, h - self.COMPOSE_H + 9, 48, 40)
        draw_round_rect(self.surface, config.ACCENT, compose_btn, radius=8)
        draw_text(self.surface, "+", compose_btn.center, self.fonts.get(24, True), config.WHITE, anchor="center")
        self._add_hit(compose_btn, "compose")

    def _draw_email_detail(self) -> None:
        email = self._selected_email()
        if not email:
            self.view = "emails"
            return
        w, h = self.logical_size
        
        # Header
        pygame.draw.rect(self.surface, config.HEADER, pygame.Rect(0, 0, w, self.HEADER_H))
        self._icon_button(pygame.Rect(8, 12, 38, 38), "back", "back")
        
        f_title = self.fonts.get(16, True)
        draw_text(self.surface, truncate(f_title, email.display_subject(), w - 180), (54, 12), f_title, config.TEXT)
        
        # Botões
        self._icon_button(pygame.Rect(w - 136, 12, 34, 34), "star", "star")
        self._icon_button(pygame.Rect(w - 96, 12, 34, 34), "important", "important")
        self._icon_button(pygame.Rect(w - 56, 12, 34, 34), "delete", "delete")
        
        # Email body
        viewport = self._email_viewport()
        pygame.draw.rect(self.surface, config.BG_CHAT, viewport)
        items, total = self._email_layout()
        content_top = viewport.bottom - total + self.scroll
        if total < viewport.height:
            content_top = viewport.bottom - total
        
        for item in items:
            kind = item[0]
            if kind == "header":
                _, em, top, h = item
                y = content_top + top
                if y + h < viewport.y or y > viewport.bottom:
                    continue
                # Avatar
                draw_avatar(self.surface, (40, y + 24), 20, em.display_sender(), self.fonts.get(11, True))
                # Sender
                f_sender = self.fonts.get(14, True)
                draw_text(self.surface, truncate(f_sender, em.display_sender(), w - 80), (70, y + 8), f_sender, config.TEXT)
                # Time
                f_time = self.fonts.get(11)
                draw_text(self.surface, format_full_time(em.ts), (w - 14, y + 10), f_time, config.TEXT_DIM, anchor="topright")
                # To
                f_to = self.fonts.get(11)
                to_text = ", ".join(em.recipients) if em.recipients else "(sem destinatário)"
                draw_text(self.surface, truncate(f_to, f"Para: {to_text}", w - 80), (70, y + 30), f_to, config.TEXT_DIM)
                # Divider
                pygame.draw.rect(self.surface, config.DIVIDER, pygame.Rect(16, y + 70, w - 32, 1))
            elif kind == "body":
                _, em, top, h, lines = item
                y = content_top + top
                if y + h < viewport.y - 20 or y > viewport.bottom + 20:
                    continue
                f_text = self.fonts.get(15)
                ty = y + 12
                for line in lines:
                    draw_text(self.surface, line, (16, ty), f_text, config.TEXT)
                    ty += f_text.get_height() + 2
        
        # Scrollbar
        if total > viewport.height:
            vis = viewport.height / total
            offset = 1.0 - (self.scroll / self._max_scroll()) if self._max_scroll() > 0 else 1.0
            draw_scrollbar(self.surface, pygame.Rect(w - 6, viewport.y + 6, 4, viewport.height - 12), vis, offset)
        
        # Compose bar (reply)
        bar = pygame.Rect(0, h - self.COMPOSE_H, w, self.COMPOSE_H)
        pygame.draw.rect(self.surface, config.HEADER_2, bar)
        pygame.draw.rect(self.surface, config.DIVIDER, pygame.Rect(bar.x, bar.y, bar.width, 1))
        field = pygame.Rect(14, bar.y + 9, bar.width - 80, bar.height - 18)
        draw_round_rect(self.surface, config.PANEL_2, field, radius=20)
        f = self.fonts.get(13)
        draw_text(self.surface, truncate(f, "Responder...", field.width - 24), (field.x + 14, field.y + 8), f, config.TEXT_DIM)
        self._add_hit(field, "compose")
        send = pygame.Rect(bar.right - 56, bar.y + 9, 40, 40)
        draw_round_rect(self.surface, config.PANEL_2, send, radius=20)
        draw_text(self.surface, "➤", send.center, self.fonts.get(16, True), config.TEXT_DIM, anchor="center")
        self._add_hit(send, "send")

    def _draw_compose(self) -> None:
        w, h = self.logical_size
        
        # Header
        pygame.draw.rect(self.surface, config.HEADER, pygame.Rect(0, 0, w, self.HEADER_H))
        self._icon_button(pygame.Rect(8, 12, 38, 38), "back", "back")
        f_title = self.fonts.get(16, True)
        draw_text(self.surface, "Novo email", (54, 12), f_title, config.TEXT)
        send_btn = pygame.Rect(w - 64, 12, 48, 40)
        draw_round_rect(self.surface, config.ACCENT, send_btn, radius=8)
        draw_text(self.surface, "➤", send_btn.center, self.fonts.get(16, True), config.WHITE, anchor="center")
        self._add_hit(send_btn, "send")
        
        # Fields
        viewport = pygame.Rect(0, self.HEADER_H, w, h - self.HEADER_H)
        pygame.draw.rect(self.surface, config.BG_CHAT, viewport)
        
        y = self.HEADER_H + 16
        f_label = self.fonts.get(12, True)
        f_value = self.fonts.get(14)
        
        # Para
        draw_text(self.surface, "Para:", (16, y), f_label, config.TEXT_DIM)
        to_field = pygame.Rect(16, y + 20, w - 32, 36)
        draw_round_rect(self.surface, config.PANEL_2, to_field, radius=8)
        draw_text(self.surface, truncate(f_value, self.compose_to or "Toque para digitar...", to_field.width - 20), (to_field.x + 12, to_field.y + 8), f_value, config.TEXT if self.compose_to else config.TEXT_DIM)
        self._add_hit(to_field, "compose_to_field")
        y += 64
        
        # Assunto
        draw_text(self.surface, "Assunto:", (16, y), f_label, config.TEXT_DIM)
        subj_field = pygame.Rect(16, y + 20, w - 32, 36)
        draw_round_rect(self.surface, config.PANEL_2, subj_field, radius=8)
        draw_text(self.surface, truncate(f_value, self.compose_subject or "Toque para digitar...", subj_field.width - 20), (subj_field.x + 12, subj_field.y + 8), f_value, config.TEXT if self.compose_subject else config.TEXT_DIM)
        self._add_hit(subj_field, "compose_subject_field")
        y += 64
        
        # Mensagem
        draw_text(self.surface, "Mensagem:", (16, y), f_label, config.TEXT_DIM)
        body_field = pygame.Rect(16, y + 20, w - 32, h - y - 80)
        draw_round_rect(self.surface, config.PANEL_2, body_field, radius=8)
        body_lines = wrap_text(f_value, self.compose_body or "Toque para digitar...", body_field.width - 20)
        ty = body_field.y + 8
        for line in body_lines[:20]:
            draw_text(self.surface, line, (body_field.x + 12, ty), f_value, config.TEXT if self.compose_body else config.TEXT_DIM)
            ty += f_value.get_height() + 2
        self._add_hit(body_field, "compose_body_field")

    def _draw_modal(self, now: float) -> None:
        dim = pygame.Surface(self.logical_size, pygame.SRCALPHA)
        dim.fill((0, 0, 0, 165))
        self.surface.blit(dim, (0, 0))
        if self.modal == "settings":
            self._draw_settings()
        elif self.modal == "accounts":
            self._draw_accounts()
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
        panel = self._panel(620, 480)
        draw_text(self.surface, "Configurações", (panel.x + 22, panel.y + 16), self.fonts.get(19, True), config.TEXT)
        draw_text(self.surface, config.APP_VERSION, (panel.right - 22, panel.y + 20), self.fonts.get(11), config.TEXT_FAINT, anchor="topright")
        rows = self._settings_rows()
        y = panel.y + 58
        f = self.fonts.get(13)
        fv = self.fonts.get(12)
        for i, row in enumerate(rows):
            r = pygame.Rect(panel.x + 14, y, panel.width - 28, 34)
            if i == self._settings_index:
                draw_round_rect(self.surface, config.SELECT, r, radius=7)
                pygame.draw.rect(self.surface, config.ACCENT, pygame.Rect(r.x, r.y + 6, 3, r.height - 12), border_radius=2)
            draw_text(self.surface, row["label"], (r.x + 14, r.y + 8), f, config.TEXT)
            if row.get("value"):
                draw_text(self.surface, truncate(fv, row["value"], r.width - 220), (r.right - 12, r.y + 9), fv, config.TEXT_DIM, anchor="topright")
            self._add_hit(r, f"settings_row:{i}")
            y += 36
        stats = self.store.stats()
        footer_y = panel.bottom - 54
        pygame.draw.rect(self.surface, config.DIVIDER, pygame.Rect(panel.x + 14, footer_y - 8, panel.width - 28, 1))
        draw_text(self.surface, f"Emails: {stats['emails']} · Contas: {stats['accounts']}", (panel.x + 22, footer_y), self.fonts.get(10), config.TEXT_FAINT)
        draw_text(self.surface, "↑↓ navegar · Enter ativar · Esc fechar", (panel.right - 22, footer_y), self.fonts.get(10), config.TEXT_FAINT, anchor="topright")

    def _draw_accounts(self) -> None:
        panel = self._panel(620, 420)
        draw_text(self.surface, "Contas de email", (panel.x + 22, panel.y + 16), self.fonts.get(19, True), config.TEXT)
        accounts = self.backend.accounts()
        if not accounts:
            f = self.fonts.get(13)
            draw_text(self.surface, "Nenhuma conta configurada.", (panel.centerx, panel.y + 80), f, config.TEXT_DIM, anchor="midtop")
            draw_text(self.surface, "Adicione uma conta IMAP/SMTP para começar.", (panel.centerx, panel.y + 110), self.fonts.get(12), config.TEXT_FAINT, anchor="midtop")
        else:
            y = panel.y + 60
            for acc in accounts:
                r = pygame.Rect(panel.x + 14, y, panel.width - 28, 48)
                draw_round_rect(self.surface, config.PANEL_2, r, radius=8)
                f_name = self.fonts.get(14, True)
                f_email = self.fonts.get(12)
                draw_text(self.surface, truncate(f_name, acc.display_name(), r.width - 40), (r.x + 14, r.y + 8), f_name, config.TEXT)
                draw_text(self.surface, truncate(f_email, acc.email, r.width - 40), (r.x + 14, r.y + 26), f_email, config.TEXT_DIM)
                y += 56
        self._pill_button(pygame.Rect(panel.right - 130, panel.bottom - 54, 106, 36), "Fechar", "settings_close")

    def _draw_about(self) -> None:
        panel = self._panel(620, 420)
        draw_text(self.surface, "Sobre", (panel.x + 22, panel.y + 16), self.fonts.get(19, True), config.TEXT)
        f = self.fonts.get(13)
        f_small = self.fonts.get(11)
        y = panel.y + 58
        paragraphs = [
            ("O que é", True),
            ("PortMail é um port de email para PortMaster, com UI em pygame.", False),
            ("Funcionalidades", True),
            ("Modo demo offline, backend IMAP/SMTP real, busca, envio de emails.", False),
            ("Limites", True),
            ("Requer configuração de conta IMAP/SMTP. Não suporta anexos.", False),
            ("Dados", True),
            (f"Emails e configurações ficam em: {self.data_dir}", False),
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
        self._pill_button(pygame.Rect(panel.right - 130, panel.bottom - 54, 106, 36), "Fechar", "about_close")

    def _add_hit(self, rect: pygame.Rect, action: str) -> None:
        self._hits.append((pygame.Rect(rect), action))

    def _hit(self, pos: tuple[int, int]) -> Optional[str]:
        for rect, action in reversed(self._hits):
            if rect.collidepoint(pos):
                return action
        return None

    def _pill_button(self, rect: pygame.Rect, label: str, action: str, accent: bool = False) -> None:
        draw_round_rect(self.surface, config.ACCENT if accent else config.PANEL_2, rect, radius=9)
        draw_text(self.surface, label, rect.center, self.fonts.get(13, True), config.WHITE if accent else config.TEXT, anchor="center")
        self._add_hit(rect, action)

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
        elif icon == "star":
            points = []
            import math
            for i in range(10):
                angle = math.pi / 2 + i * math.pi / 5
                r = 8 if i % 2 == 0 else 3
                points.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
            pygame.draw.polygon(self.surface, c, points)
        elif icon == "important":
            pygame.draw.polygon(self.surface, c, [(cx, cy - 8), (cx + 8, cy + 6), (cx - 8, cy + 6)])
        elif icon == "delete":
            pygame.draw.rect(self.surface, c, pygame.Rect(cx - 6, cy - 4, 12, 10), 2)
            pygame.draw.line(self.surface, c, (cx - 8, cy - 6), (cx + 8, cy - 6), 2)
            pygame.draw.line(self.surface, c, (cx - 3, cy - 8), (cx + 3, cy - 8), 2)
        elif icon == "close":
            pygame.draw.line(self.surface, c, (cx - 5, cy - 5), (cx + 5, cy + 5), 2)
            pygame.draw.line(self.surface, c, (cx + 5, cy - 5), (cx - 5, cy + 5), 2)
        self._add_hit(rect, action)
