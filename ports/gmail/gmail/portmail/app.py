"""Tela do PortMail.

Fica em cima do `BaseApp` do core: aqui so tem a logica do PortMail (lista,
detalhe, escrita, pastas e conta). Janela, avisos, teclado virtual e o
desenho basico vem do core.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import pygame

from core.app import BaseApp
from core.ui import widgets
from core.ui.avatars import initials, preview

from . import config
from .backend import make_backend
from .models import Account, Email, format_full_time, format_time
from .store import Store
from .theme import THEME

TOP_H = 38
TAB_H = 26
SEARCH_H = 34
ROW_H = 58
HINT_H = 20


class PortMailApp(BaseApp):
    """Cliente de email em tela cheia."""

    def __init__(
        self,
        backend_kind: Optional[str] = None,
        fullscreen: Optional[bool] = None,
        window_size: Optional[tuple[int, int]] = None,
        data_dir: Optional[Path] = None,
        headless: bool = False,
    ):
        super().__init__(
            theme=THEME,
            fullscreen=config.fullscreen_override() if fullscreen is None else fullscreen,
            window_size=window_size,
            headless=headless,
        )
        self.logical_size = (config.LOGICAL_W, config.LOGICAL_H)
        self.surface = pygame.Surface(self.logical_size)

        self.data_dir = Path(data_dir) if data_dir else config.data_dir()
        self.store = Store(self.data_dir / "mail.sqlite3")

        saved = self.store.meta_get("backend", "demo")
        self.backend_kind = (backend_kind or saved or "demo").lower()
        if self.backend_kind not in ("demo", "imap"):
            self.backend_kind = "demo"
        self.backend = make_backend(self.backend_kind, self.store, self.data_dir)
        self.backend.start()

        self.view = "list"                 # list | detail | compose
        self.modal: Optional[str] = None   # settings | account | about | confirm
        self.modal_index = 0
        self.folder = "INBOX"
        self.folder_index = 0
        self.emails: list[Email] = []
        self.list_index = 0
        self.scroll = 0.0
        self.detail_scroll = 0.0
        self.selected_id: Optional[str] = None
        self.search = ""
        self.search_active = False
        self.focus_field = 0
        self.compose_to = ""
        self.compose_subject = ""
        self.compose_body = ""
        self.pending_delete: Optional[str] = None
        self._last_refresh = 0.0

        pygame.display.set_caption(f"{config.APP_NAME} - OddHub")
        self._load_emails()

    # -- dados --------------------------------------------------------------
    def _account(self) -> Optional[Account]:
        return self.backend.default_account()

    def _load_emails(self) -> None:
        account = self._account()
        self.emails = self.backend.emails(account.id, self.folder, 200) if account else []
        if self.list_index >= len(self.emails):
            self.list_index = max(0, len(self.emails) - 1)
        self._last_refresh = time.time()

    def _selected(self) -> Optional[Email]:
        if not self.selected_id:
            return None
        for email in self.emails:
            if email.id == self.selected_id:
                return email
        return self.backend.email(self.selected_id)

    def _unread_count(self, folder: str) -> int:
        account = self._account()
        if not account:
            return 0
        if folder == "INBOX":
            return self.store.count_unread(account.id, folder)
        return 0

    # -- acoes --------------------------------------------------------------
    def _open_email(self, email_id: str) -> None:
        self.selected_id = email_id
        email = self.backend.email(email_id)
        if email and not email.is_read:
            self.backend.mark_read(email_id, True)
        self.view = "detail"
        self.detail_scroll = 0.0

    def _back(self) -> None:
        """Volta um nivel. O app so sai pelo Select+Start do PortMaster."""
        if self.keyboard.active:
            self.keyboard.cancel()
            return
        if self.modal:
            self.modal = None
            return
        if self.view == "detail":
            self.view = "list"
            self.selected_id = None
            return
        if self.view == "compose":
            self.view = "list"
            return
        if self.search_active or self.search:
            self.search = ""
            self.search_active = False
            self._load_emails()
            return

    def _switch_folder(self, delta: int) -> None:
        self.folder_index = (self.folder_index + delta) % len(config.FOLDERS)
        self.folder = config.FOLDERS[self.folder_index]
        self.list_index = 0
        self.scroll = 0.0
        self._load_emails()

    def _toggle_star(self) -> None:
        if not self.selected_id:
            return
        self.backend.toggle_star(self.selected_id)
        email = self.backend.email(self.selected_id)
        self.toast_message(
            "Desmarcado" if email and not email.is_starred else "Marcado com estrela", "ok"
        )
        self._load_emails()

    def _ask_delete(self) -> None:
        if not self.selected_id:
            return
        self.pending_delete = self.selected_id
        self.modal = "confirm"
        self.modal_index = 0

    def _do_delete(self) -> None:
        if self.pending_delete:
            self.backend.delete_email(self.pending_delete)
            self.toast_message("Email apagado", "ok")
        self.pending_delete = None
        self.modal = None
        self.view = "list"
        self.selected_id = None
        self._load_emails()

    def _open_search(self) -> None:
        self.search_active = True
        self.keyboard.open("Buscar email", self.search, self._set_search, max_len=80)

    def _set_search(self, text: str) -> None:
        self.search = text.strip()
        self.search_active = bool(self.search)
        self.list_index = 0
        self.scroll = 0.0
        self._load_emails()

    def _open_compose(self) -> None:
        self.view = "compose"
        self.focus_field = 0
        self.compose_to = ""
        self.compose_subject = ""
        self.compose_body = ""

    def _edit_field(self, index: int) -> None:
        self.focus_field = index
        values = (self.compose_to, self.compose_subject, self.compose_body)
        titles = ("Para:", "Assunto:", "Mensagem:")
        limits = (200, 150, 4000)
        self.keyboard.open(titles[index], values[index], self._set_field, max_len=limits[index])

    def _set_field(self, text: str) -> None:
        if self.focus_field == 0:
            self.compose_to = text.strip()
        elif self.focus_field == 1:
            self.compose_subject = text.strip()
        else:
            self.compose_body = text
        if self.focus_field < 2:
            self.focus_field += 1

    def _send(self) -> None:
        if not self.compose_to:
            self.toast_message("Informe o destinatario", "warn")
            return
        if not self.compose_body:
            self.toast_message("Escreva a mensagem", "warn")
            return
        recipients = [r.strip() for r in self.compose_to.split(",") if r.strip()]
        sent = self.backend.send(recipients, self.compose_subject, self.compose_body)
        if sent is None:
            self.toast_message("Falha ao enviar", "error")
            return
        self.toast_message("Email enviado", "ok")
        self.view = "list"
        self.folder = "SENT"
        self.folder_index = config.FOLDERS.index("SENT")
        self._load_emails()

    # -- configuracoes ------------------------------------------------------
    def _open_settings(self) -> None:
        self.modal = "settings"
        self.modal_index = 0

    def _settings_rows(self) -> list[dict]:
        account = self._account()
        stats = self.store.stats()
        return [
            {"label": "Modo", "value": self.backend.label, "action": "toggle"},
            {"label": "Estado", "value": self.backend.status_label(), "action": "none"},
            {"label": "Conta", "value": account.display() if account else "nenhuma", "action": "account"},
            {"label": "Emails", "value": str(stats["emails"]), "action": "none"},
            {"label": "Sincronizar", "value": "buscar agora", "action": "refresh"},
            {"label": "Sobre", "value": "informacoes do port", "action": "about"},
            {"label": "Fechar", "value": "", "action": "close"},
        ]

    def _activate(self, action: str) -> None:
        if action in ("none", ""):
            return
        if action == "toggle":
            self._toggle_backend()
        elif action == "account":
            self.modal = "account"
            self.modal_index = 0
        elif action == "refresh":
            self.backend.refresh()
            self.toast_message("Sincronizando", "info")
        elif action == "about":
            self.modal = "about"
        elif action == "close":
            self.modal = None

    def _toggle_backend(self) -> None:
        target = "imap" if self.backend_kind == "demo" else "demo"
        try:
            self.backend.stop()
        except Exception:
            pass
        self.backend_kind = target
        self.store.meta_set("backend", target)
        self.backend = make_backend(target, self.store, self.data_dir)
        self.backend.start()
        self._load_emails()
        if target == "imap":
            self.modal = "account"
            self.toast_message("Conectando na conta...", "info")
        else:
            self.modal = None
            self.toast_message("Modo demo", "ok")

    def _account_rows(self) -> list[dict]:
        account = self._account()
        return [
            {"label": "Email", "value": account.email if account else "", "action": "email"},
            {"label": "Senha", "value": "definida" if account and account.password else "vazia",
             "action": "password"},
            {"label": "IMAP", "value": f"{account.imap_host}:{account.imap_port}" if account else "",
             "action": "imap"},
            {"label": "SMTP", "value": f"{account.smtp_host}:{account.smtp_port}" if account else "",
             "action": "smtp"},
            {"label": "Salvar", "value": "gravar e conectar", "action": "save"},
            {"label": "Voltar", "value": "", "action": "close"},
        ]

    def _edit_account_field(self, action: str) -> None:
        account = self._account() or Account(id="conta:gmail")
        if action == "email":
            self.keyboard.open("Email", account.email, self._set_account_email, max_len=120)
        elif action == "password":
            self.keyboard.open("Senha", account.password, self._set_account_password, max_len=120)
        elif action == "imap":
            self.keyboard.open("Servidor IMAP", account.imap_host, self._set_account_imap, max_len=120)
        elif action == "smtp":
            self.keyboard.open("Servidor SMTP", account.smtp_host, self._set_account_smtp, max_len=120)
        elif action == "save":
            self.store.save_account(account)
            self.backend.save_account(account)
            self.toast_message("Conta salva", "ok")
            self.modal = "settings"
            if self.backend_kind == "imap":
                self.backend.refresh()
        elif action == "close":
            self.modal = "settings"

    def _set_account_email(self, text: str) -> None:
        account = self._account() or Account(id="conta:gmail")
        account.email = text.strip()
        self.store.save_account(account)
        self._load_emails()

    def _set_account_password(self, text: str) -> None:
        account = self._account() or Account(id="conta:gmail")
        account.password = text
        self.store.save_account(account)

    def _set_account_imap(self, text: str) -> None:
        account = self._account() or Account(id="conta:gmail")
        value = text.strip()
        if ":" in value:
            host, port = value.rsplit(":", 1)
            account.imap_host = host.strip()
            try:
                account.imap_port = int(port)
            except ValueError:
                pass
        else:
            account.imap_host = value
        self.store.save_account(account)

    def _set_account_smtp(self, text: str) -> None:
        account = self._account() or Account(id="conta:gmail")
        value = text.strip()
        if ":" in value:
            host, port = value.rsplit(":", 1)
            account.smtp_host = host.strip()
            try:
                account.smtp_port = int(port)
            except ValueError:
                pass
        else:
            account.smtp_host = value
        self.store.save_account(account)

    # -- eventos ------------------------------------------------------------
    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.VIDEORESIZE and not self.fullscreen and not self.headless:
                try:
                    self._window = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                except pygame.error:
                    pass
                continue
            if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
                self._mouse = event.pos

            if self.keyboard.active:
                if self.keyboard.handle_event(event):
                    continue

            if event.type == pygame.TEXTINPUT:
                # Com o teclado virtual aberto ele cuida do proprio texto.
                if not self.keyboard.active:
                    self._on_text_input(event.text)
                continue

            if self.modal:
                if self._handle_modal(event):
                    continue

            if event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_mouse(event)
            elif event.type == pygame.MOUSEWHEEL:
                self._handle_wheel(event)

    def _on_text_input(self, text: str) -> None:
        """Caractere digitado no teclado fisico (ou vindo de um OSK do sistema)."""
        if not text:
            return
        if self.view == "compose":
            if self.focus_field == 0:
                self.compose_to += text
            elif self.focus_field == 1:
                self.compose_subject += text
            else:
                self.compose_body += text
        elif self.search_active:
            self.search += text
            self._load_emails()

    def _handle_key(self, event: pygame.event.Event) -> None:
        key = event.key
        if key == pygame.K_F12:
            self._toggle_osk()
            return
        if key == pygame.K_F1:
            self._open_settings()
            return
        if key == pygame.K_ESCAPE:
            self._back()
            return
        if key == pygame.K_TAB:
            self._switch_folder(1)
            return
        if key == pygame.K_UP:
            self._move(-1)
        elif key == pygame.K_DOWN:
            self._move(1)
        elif key == pygame.K_LEFT:
            if self.view == "list":
                self._switch_folder(-1)
        elif key == pygame.K_RIGHT:
            if self.view == "list":
                self._switch_folder(1)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._activate_current()
        elif key == pygame.K_SPACE:
            if self.view == "detail":
                self._toggle_star()
        elif key in (pygame.K_PAGEUP, pygame.K_KP9):
            self._scroll(-1)
        elif key in (pygame.K_PAGEDOWN, pygame.K_KP3):
            self._scroll(1)
        elif key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            if self.view == "detail":
                self._ask_delete()
        elif event.unicode and event.unicode.isprintable():
            if self.view == "compose":
                self._on_text_input(event.unicode)
            elif self.view == "list":
                self.search_active = True
                self.search += event.unicode
                self._load_emails()

    def _move(self, delta: int) -> None:
        if self.view == "list":
            if self.emails:
                self.list_index = (self.list_index + delta) % len(self.emails)
                self._ensure_visible()
        elif self.view == "detail":
            self.detail_scroll -= delta * 60
        elif self.view == "compose":
            self.focus_field = max(0, min(2, self.focus_field + delta))

    def _scroll(self, direction: int) -> None:
        if self.view == "list":
            if self.emails:
                self.list_index = max(0, min(len(self.emails) - 1, self.list_index + direction * 5))
                self._ensure_visible()
        elif self.view == "detail":
            self.detail_scroll -= direction * 90

    def _activate_current(self) -> None:
        if self.view == "list":
            if self.emails:
                self._open_email(self.emails[self.list_index].id)
        elif self.view == "detail":
            self._toggle_star()
        elif self.view == "compose":
            self._edit_field(self.focus_field)

    def _toggle_osk(self) -> None:
        """L2 (F12) abre e fecha o teclado virtual."""
        if self.keyboard.active:
            self.keyboard.cancel()
            return
        if self.view == "compose":
            self._edit_field(self.focus_field)
        elif self.view == "list":
            self._open_search()

    def _handle_mouse(self, event: pygame.event.Event) -> None:
        action = self.hit(event.pos)
        if not action:
            return
        if action.startswith("row:"):
            index = int(action.split(":", 1)[1])
            if 0 <= index < len(self.emails):
                self.list_index = index
                self._open_email(self.emails[index].id)
        elif action.startswith("tab:"):
            self.folder_index = int(action.split(":", 1)[1]) % len(config.FOLDERS)
            self.folder = config.FOLDERS[self.folder_index]
            self.list_index = 0
            self._load_emails()
        elif action.startswith("settings_row:"):
            index = int(action.split(":", 1)[1])
            rows = self._settings_rows()
            if 0 <= index < len(rows):
                self.modal_index = index
                self._activate(rows[index]["action"])
        elif action.startswith("account_row:"):
            index = int(action.split(":", 1)[1])
            rows = self._account_rows()
            if 0 <= index < len(rows):
                self.modal_index = index
                self._edit_account_field(rows[index]["action"])
        elif action.startswith("confirm_row:"):
            index = int(action.split(":", 1)[1])
            self.modal_index = index
            if index == 0:
                self._do_delete()
            else:
                self.modal = None
        elif action == "search":
            self._open_search()
        elif action == "clear_search":
            self.search = ""
            self.search_active = False
            self._load_emails()
        elif action == "settings":
            self._open_settings()
        elif action == "back":
            self._back()
        elif action == "compose":
            self._open_compose()
        elif action == "send":
            self._send()
        elif action == "star":
            self._toggle_star()
        elif action == "delete":
            self._ask_delete()
        elif action == "close":
            self.modal = None

    def _handle_wheel(self, event: pygame.event.Event) -> None:
        if self.view == "detail":
            self.detail_scroll += event.y * 40
        elif self.view == "list" and self.emails:
            self.list_index = int(widgets.clamp(self.list_index + event.y, 0, len(self.emails) - 1))
            self._ensure_visible()

    def _handle_modal(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.modal = None
            return True
        if self.modal in ("settings", "account"):
            rows = self._settings_rows() if self.modal == "settings" else self._account_rows()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.modal_index = max(0, self.modal_index - 1)
                    return True
                if event.key == pygame.K_DOWN:
                    self.modal_index = min(len(rows) - 1, self.modal_index + 1)
                    return True
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.modal == "settings":
                        self._activate(rows[self.modal_index]["action"])
                    else:
                        self._edit_account_field(rows[self.modal_index]["action"])
                    return True
        elif self.modal == "about":
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.modal = None
                return True
        elif self.modal == "confirm":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.modal_index = 0
                    return True
                if event.key == pygame.K_DOWN:
                    self.modal_index = 1
                    return True
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.modal_index == 0:
                        self._do_delete()
                    else:
                        self.modal = None
                    return True
        return False

    # -- ciclo --------------------------------------------------------------
    def update(self, dt: float) -> None:
        now = time.time()
        try:
            self.backend.tick(now)
        except Exception:
            pass
        for event in self.backend.poll():
            if event.kind == "emails":
                self._load_emails()
            elif event.kind == "error":
                self.toast_message(event.data.get("text", "Erro"), "error")
        if now - self._last_refresh > 5.0:
            self._load_emails()
        if self.view == "detail":
            self.detail_scroll = widgets.clamp(self.detail_scroll, 0, self._max_detail_scroll())

    def shutdown(self) -> None:
        try:
            self.backend.stop()
        except Exception:
            pass
        try:
            self.store.close()
        except Exception:
            pass
        super().shutdown()

    # -- layout -------------------------------------------------------------
    def _list_top(self) -> int:
        top = TOP_H + TAB_H
        if self.search_active or self.search:
            top += SEARCH_H
        return top

    def _list_viewport(self) -> pygame.Rect:
        width, height = self.logical_size
        top = self._list_top()
        return pygame.Rect(0, top, width, height - top - HINT_H)

    def _max_scroll(self) -> float:
        viewport = self._list_viewport()
        return max(0.0, len(self.emails) * ROW_H - viewport.height)

    def _ensure_visible(self) -> None:
        viewport = self._list_viewport()
        top = self.list_index * ROW_H
        bottom = top + ROW_H
        if top - self.scroll < 0:
            self.scroll = float(top)
        elif bottom - self.scroll > viewport.height:
            self.scroll = float(bottom - viewport.height)
        self.scroll = widgets.clamp(self.scroll, 0, self._max_scroll())

    def _detail_viewport(self) -> pygame.Rect:
        width, height = self.logical_size
        return pygame.Rect(0, TOP_H, width, height - TOP_H - HINT_H)

    def _detail_lines(self) -> tuple[list, float]:
        email = self._selected()
        if email is None:
            return [], 0.0
        viewport = self._detail_viewport()
        pad = 14
        width = viewport.width - pad * 2
        f_title = self.fonts.get(17, True)
        f_meta = self.fonts.get(12)
        f_body = self.fonts.get(13)

        blocks = []
        y = pad
        for line in widgets.wrap_text(f_title, email.display_subject(), width, max_lines=3):
            blocks.append(("subject", line, y, f_title, self.theme.text))
            y += f_title.get_height() + 2
        y += 4

        blocks.append(("meta", "De: " + email.display_sender(), y, f_meta, self.theme.text_dim))
        y += f_meta.get_height() + 2
        if email.to:
            blocks.append(("meta", "Para: " + ", ".join(email.to), y, f_meta, self.theme.text_dim))
            y += f_meta.get_height() + 2
        if email.ts:
            blocks.append(("meta", format_full_time(email.ts), y, f_meta, self.theme.text_faint))
            y += f_meta.get_height() + 2
        y += 8
        pygame.draw.line(self.surface, self.theme.divider, (pad, y), (viewport.width - pad, y))
        y += 10

        for line in widgets.wrap_text(f_body, email.body or "(sem corpo)", width):
            blocks.append(("body", line, y, f_body, self.theme.text))
            y += f_body.get_height() + 3
        return blocks, float(y + pad)

    def _max_detail_scroll(self) -> float:
        _blocks, total = self._detail_lines()
        return max(0.0, total - self._detail_viewport().height)

    # -- desenho ------------------------------------------------------------
    def draw(self) -> None:
        now = time.time()
        self._hits = []
        self.surface.fill(self.theme.bg)

        if self.view == "list":
            self._draw_list()
        elif self.view == "detail":
            self._draw_detail()
        elif self.view == "compose":
            self._draw_compose()

        if self.modal:
            self.modal_backdrop()
            if self.modal == "settings":
                self._draw_settings()
            elif self.modal == "account":
                self._draw_account()
            elif self.modal == "about":
                self._draw_about()
            elif self.modal == "confirm":
                self._draw_confirm()

        self.keyboard.draw(self.surface, now)
        self.draw_toast(now)

    def _draw_top_bar(self, title: str, back: bool = False) -> None:
        width, _height = self.logical_size
        pygame.draw.rect(self.surface, self.theme.header, pygame.Rect(0, 0, width, TOP_H))
        pygame.draw.rect(self.surface, self.theme.divider, pygame.Rect(0, TOP_H - 1, width, 1))
        x = 10
        if back:
            self.icon_button(pygame.Rect(x, 6, 26, 26), "back", "back")
            x += 32
        f_title = self.fonts.get(15, True)
        widgets.draw_text(
            self.surface,
            widgets.truncate(f_title, title, width - x - 80),
            (x, 10),
            f_title,
            self.theme.text,
        )
        if not back:
            self.icon_button(pygame.Rect(width - 76, 6, 26, 26), "search", "search")
            self.icon_button(pygame.Rect(width - 42, 6, 26, 26), "gear", "settings")

    def _draw_tabs(self) -> None:
        width, _height = self.logical_size
        pygame.draw.rect(self.surface, self.theme.header_2, pygame.Rect(0, TOP_H, width, TAB_H))
        f_tab = self.fonts.get(12, True)
        x = 8
        for index, folder in enumerate(config.FOLDERS):
            label = config.FOLDER_LABELS.get(folder, folder)
            count = self._unread_count(folder)
            text = f"{label} ({count})" if count else label
            tab_w = f_tab.size(text)[0] + 18
            tab = pygame.Rect(x, TOP_H + 3, tab_w, TAB_H - 6)
            if folder == self.folder:
                widgets.draw_round_rect(self.surface, self.theme.select, tab, radius=5)
                pygame.draw.rect(
                    self.surface,
                    self.theme.accent,
                    pygame.Rect(tab.x, tab.bottom - 2, tab.width, 2),
                )
            widgets.draw_text(
                self.surface,
                text,
                (tab.x + 9, tab.y + 3),
                f_tab,
                self.theme.text if folder == self.folder else self.theme.text_dim,
            )
            self.add_hit(tab, f"tab:{index}")
            x += tab_w + 6

    def _draw_list(self) -> None:
        width, height = self.logical_size
        account = self._account()
        title = account.display() if account else config.APP_NAME
        self._draw_top_bar(title)
        self._draw_tabs()

        top = TOP_H + TAB_H
        if self.search_active or self.search:
            field = pygame.Rect(8, top + 4, width - 16, SEARCH_H - 8)
            widgets.draw_round_rect(self.surface, self.theme.panel_2, field, radius=14)
            pygame.draw.rect(self.surface, self.theme.accent, field, width=1, border_radius=14)
            font = self.fonts.get(13)
            widgets.draw_text(
                self.surface,
                widgets.truncate(font, self.search or "Buscar...", field.width - 50),
                (field.x + 12, field.y + 6),
                font,
                self.theme.text if self.search else self.theme.text_faint,
            )
            self.icon_button(pygame.Rect(field.right - 26, field.y + 3, 20, 20), "close", "clear_search")
            top += SEARCH_H

        viewport = self._list_viewport()
        pygame.draw.rect(self.surface, self.theme.bg, viewport)

        if not self.emails:
            widgets.draw_text(
                self.surface,
                "Nenhum email aqui.",
                (viewport.centerx, viewport.y + 60),
                self.fonts.get(13),
                self.theme.text_dim,
                anchor="midtop",
            )
            widgets.draw_text(
                self.surface,
                "Use Configuracoes para conectar uma conta.",
                (viewport.centerx, viewport.y + 82),
                self.fonts.get(11),
                self.theme.text_faint,
                anchor="midtop",
            )
            self._hint()
            return

        f_sender = self.fonts.get(13, True)
        f_subject = self.fonts.get(12)
        f_snippet = self.fonts.get(11)
        f_time = self.fonts.get(10)

        for index, email in enumerate(self.emails):
            row_y = viewport.y + index * ROW_H - self.scroll
            if row_y + ROW_H < viewport.y or row_y > viewport.bottom:
                continue
            row = pygame.Rect(0, row_y, width, ROW_H)
            if index == self.list_index:
                pygame.draw.rect(self.surface, self.theme.select, row)
                pygame.draw.rect(self.surface, self.theme.accent, pygame.Rect(0, row_y, 3, ROW_H))

            widgets.draw_avatar(
                self.surface, (30, row_y + 20), 13, email.display_sender(), self.fonts.get(10, True)
            )

            color = self.theme.text if not email.is_read else self.theme.text_dim
            widgets.draw_text(
                self.surface,
                widgets.truncate(f_sender, email.display_sender(), width - 130),
                (50, row_y + 8),
                f_sender,
                color,
            )
            if email.ts:
                widgets.draw_text(
                    self.surface,
                    format_time(email.ts),
                    (width - 12, row_y + 9),
                    f_time,
                    self.theme.accent if not email.is_read else self.theme.text_faint,
                    anchor="topright",
                )
            widgets.draw_text(
                self.surface,
                widgets.truncate(f_subject, email.display_subject(), width - 130),
                (50, row_y + 26),
                f_subject,
                color,
            )
            widgets.draw_text(
                self.surface,
                widgets.truncate(f_snippet, preview(email.body, 70), width - 130),
                (50, row_y + 42),
                f_snippet,
                self.theme.text_faint,
            )
            if email.is_starred:
                widgets.draw_icon(
                    self.surface, pygame.Rect(width - 24, row_y + 24, 14, 14), "star", self.theme.warning
                )
            if not email.is_read:
                pygame.draw.circle(self.surface, self.theme.accent, (width - 16, row_y + 8), 3)
            pygame.draw.rect(
                self.surface,
                self.theme.divider,
                pygame.Rect(50, row_y + ROW_H - 1, width - 50, 1),
            )
            self.add_hit(row, f"row:{index}")

        if len(self.emails) * ROW_H > viewport.height:
            ratio = viewport.height / (len(self.emails) * ROW_H)
            offset = self.scroll / max(1.0, self._max_scroll())
            widgets.draw_scrollbar(
                self.surface, pygame.Rect(width - 4, viewport.y + 3, 3, viewport.height - 6), ratio, offset
            )

        self._hint()

    def _draw_detail(self) -> None:
        email = self._selected()
        if email is None:
            self.view = "list"
            return
        width, height = self.logical_size
        self._draw_top_bar(email.display_subject(), back=True)

        viewport = self._detail_viewport()
        pygame.draw.rect(self.surface, self.theme.bg, viewport)
        blocks, total = self._detail_lines()
        offset = viewport.y - self.detail_scroll
        for _kind, text, y, font, color in blocks:
            screen_y = offset + y
            if screen_y + font.get_height() < viewport.y or screen_y > viewport.bottom:
                continue
            widgets.draw_text(self.surface, text, (14, screen_y), font, color)

        if total > viewport.height:
            ratio = viewport.height / total
            widgets.draw_scrollbar(
                self.surface,
                pygame.Rect(width - 4, viewport.y + 3, 3, viewport.height - 6),
                ratio,
                self.detail_scroll / max(1.0, self._max_detail_scroll()),
            )

        bar = pygame.Rect(0, height - HINT_H - 30, width, 30)
        pygame.draw.rect(self.surface, self.theme.header_2, bar)
        pygame.draw.rect(self.surface, self.theme.divider, pygame.Rect(0, bar.y, width, 1))
        self.icon_button(
            pygame.Rect(10, bar.y + 4, 22, 22),
            "star" if email.is_starred else "star_outline",
            "star",
        )
        self.icon_button(pygame.Rect(width - 32, bar.y + 4, 22, 22), "trash", "delete")
        self._hint()

    def _draw_compose(self) -> None:
        width, height = self.logical_size
        self._draw_top_bar("Novo email", back=True)

        top = TOP_H + 12
        f_label = self.fonts.get(11, True)
        f_value = self.fonts.get(13)
        values = (self.compose_to, self.compose_subject, self.compose_body)
        labels = ("Para", "Assunto", "Mensagem")
        for index in range(3):
            widgets.draw_text(self.surface, labels[index], (12, top), f_label, self.theme.text_faint)
            field_top = top + 16
            if index == 2:
                # deixa espaco para o botao ENVIAR na barra inferior
                field = pygame.Rect(12, field_top, width - 24, height - field_top - HINT_H - 48)
            else:
                field = pygame.Rect(12, field_top, width - 24, 32)
            focused = index == self.focus_field
            widgets.draw_round_rect(self.surface, self.theme.panel_2, field, radius=6)
            if focused:
                pygame.draw.rect(self.surface, self.theme.accent, field, width=1, border_radius=6)
            if index == 2:
                lines = widgets.wrap_text(
                    f_value, values[index] or "Escrever...", field.width - 20, max_lines=12
                )
                for line_index, line in enumerate(lines):
                    widgets.draw_text(
                        self.surface,
                        line,
                        (field.x + 8, field.y + 6 + line_index * (f_value.get_height() + 2)),
                        f_value,
                        self.theme.text if values[index] else self.theme.text_faint,
                    )
            else:
                widgets.draw_text(
                    self.surface,
                    widgets.truncate(f_value, values[index] or "Digitar...", field.width - 20),
                    (field.x + 8, field.y + 8),
                    f_value,
                    self.theme.text if values[index] else self.theme.text_faint,
                )
            top = field.bottom + 14

        send = pygame.Rect(width - 74, height - HINT_H - 34, 62, 26)
        widgets.draw_round_rect(self.surface, self.theme.accent, send, radius=6)
        widgets.draw_text(
            self.surface, "ENVIAR", send.center, self.fonts.get(12, True), self.theme.white, anchor="center"
        )
        self.add_hit(send, "send")
        self._hint()

    def _hint(self) -> None:
        if self.view == "detail":
            hint = "A: estrela · B: voltar · L1/R1: rolar · R2: apagar"
        elif self.view == "compose":
            hint = "A: editar · B: voltar · Y: trocar pasta"
        else:
            hint = "A: abrir · B: voltar · Y: pasta · L2: buscar"
        self.hint_bar(hint)

    def _draw_settings(self) -> None:
        panel = self.panel(460, 320)
        widgets.draw_text(
            self.surface, "Configuracoes", (panel.x + 16, panel.y + 12), self.fonts.get(16, True), self.theme.text
        )
        rows = self._settings_rows()
        y = panel.y + 46
        font = self.fonts.get(12)
        value_font = self.fonts.get(11)
        for index, row in enumerate(rows):
            rect = pygame.Rect(panel.x + 10, y, panel.width - 20, 30)
            if index == self.modal_index:
                widgets.draw_round_rect(self.surface, self.theme.select, rect, radius=6)
                pygame.draw.rect(
                    self.surface, self.theme.accent, pygame.Rect(rect.x, rect.y + 5, 3, rect.height - 10)
                )
            widgets.draw_text(self.surface, row["label"], (rect.x + 12, rect.y + 7), font, self.theme.text)
            if row.get("value"):
                widgets.draw_text(
                    self.surface,
                    widgets.truncate(value_font, row["value"], rect.width - 190),
                    (rect.right - 10, rect.y + 8),
                    value_font,
                    self.theme.text_dim,
                    anchor="topright",
                )
            self.add_hit(rect, f"settings_row:{index}")
            y += 32
        widgets.draw_text(
            self.surface,
            "Setas: navegar · Enter: ativar · Esc: fechar",
            (panel.centerx, panel.bottom - 18),
            self.fonts.get(10),
            self.theme.text_faint,
            anchor="midbottom",
        )

    def _draw_account(self) -> None:
        panel = self.panel(460, 330)
        widgets.draw_text(self.surface, "Conta", (panel.x + 16, panel.y + 12), self.fonts.get(16, True), self.theme.text)
        widgets.draw_text(
            self.surface,
            "Use a senha de aplicativo do seu provedor.",
            (panel.x + 16, panel.y + 34),
            self.fonts.get(10),
            self.theme.text_faint,
        )
        rows = self._account_rows()
        y = panel.y + 54
        font = self.fonts.get(12)
        value_font = self.fonts.get(11)
        for index, row in enumerate(rows):
            rect = pygame.Rect(panel.x + 10, y, panel.width - 20, 30)
            if index == self.modal_index:
                widgets.draw_round_rect(self.surface, self.theme.select, rect, radius=6)
                pygame.draw.rect(
                    self.surface, self.theme.accent, pygame.Rect(rect.x, rect.y + 5, 3, rect.height - 10)
                )
            widgets.draw_text(self.surface, row["label"], (rect.x + 12, rect.y + 7), font, self.theme.text)
            if row.get("value"):
                widgets.draw_text(
                    self.surface,
                    widgets.truncate(value_font, row["value"], rect.width - 150),
                    (rect.right - 10, rect.y + 8),
                    value_font,
                    self.theme.text_dim,
                    anchor="topright",
                )
            self.add_hit(rect, f"account_row:{index}")
            y += 32
        widgets.draw_text(
            self.surface,
            "Setas: navegar · Enter: editar · Esc: fechar",
            (panel.centerx, panel.bottom - 18),
            self.fonts.get(10),
            self.theme.text_faint,
            anchor="midbottom",
        )

    def _draw_about(self) -> None:
        panel = self.panel(440, 300)
        widgets.draw_text(self.surface, "Sobre", (panel.x + 16, panel.y + 12), self.fonts.get(16, True), self.theme.text)
        font = self.fonts.get(12)
        small = self.fonts.get(11)
        lines = [
            ("PortMail, cliente de email IMAP/SMTP.", True),
            ("Projeto independente, sem marca ou codigo de terceiros.", False),
            ("", False),
            ("Modo demo: mensagens de exemplo, funciona sem internet.", False),
            ("Modo conta: le e envia pela sua propria conta IMAP.", False),
            ("A senha fica guardada no cartao SD, no arquivo de dados.", False),
            ("", False),
            (f"Dados: {self.data_dir}", False),
        ]
        y = panel.y + 44
        for text, strong in lines:
            if not text:
                y += 6
                continue
            for line in widgets.wrap_text(small, text, panel.width - 32, max_lines=4):
                widgets.draw_text(
                    self.surface,
                    line,
                    (panel.x + 16, y),
                    font if strong else small,
                    self.theme.text if strong else self.theme.text_dim,
                )
                y += small.get_height() + 2
            y += 4
        widgets.draw_text(
            self.surface,
            "Enter ou Esc: fechar",
            (panel.centerx, panel.bottom - 18),
            self.fonts.get(10),
            self.theme.text_faint,
            anchor="midbottom",
        )

    def _draw_confirm(self) -> None:
        panel = self.panel(320, 160)
        widgets.draw_text(
            self.surface, "Apagar este email?", (panel.x + 16, panel.y + 14), self.fonts.get(14, True), self.theme.text
        )
        widgets.draw_text(
            self.surface, "Nao da para desfazer.", (panel.x + 16, panel.y + 36), self.fonts.get(11), self.theme.text_dim
        )
        for index, label in enumerate(("Apagar", "Cancelar")):
            rect = pygame.Rect(panel.x + 16 + index * 140, panel.y + 70, 130, 30)
            if index == self.modal_index:
                widgets.draw_round_rect(self.surface, self.theme.select, rect, radius=6)
                pygame.draw.rect(
                    self.surface,
                    self.theme.accent if index == 0 else self.theme.danger,
                    pygame.Rect(rect.x, rect.y + 5, 3, rect.height - 10),
                )
            widgets.draw_text(self.surface, label, (rect.x + 12, rect.y + 7), self.fonts.get(12), self.theme.text)
            self.add_hit(rect, f"confirm_row:{index}")
        widgets.draw_text(
            self.surface,
            "Setas: escolher · Enter: confirmar · Esc: cancelar",
            (panel.centerx, panel.bottom - 16),
            self.fonts.get(10),
            self.theme.text_faint,
            anchor="midbottom",
        )
