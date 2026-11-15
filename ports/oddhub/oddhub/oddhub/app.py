"""Tela do gerenciador OddHub.

Visual de loja de apps: fundo claro, cards com acento por categoria, atalhos
embaixo. O conteudo vem do manifesto da colecao e dos ports instalados no
cartao.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

import pygame

from core.app import BaseApp
from core.ui import widgets

from . import manifest as manifest_mod
from .config import APP_NAME, APP_VERSION
from .theme import CATEGORY_COLORS, CATEGORY_INITIALS, THEME

TOP_H = 52
TABS_Y = 62
TABS_H = 32
BOTTOM_H = 44

CARD_W = 292
CARD_H = 150
GAP = 16
PAGE_SIZE = 4


class HubApp(BaseApp):
    """Lista os ports da colecao e abre o escolhido."""

    def __init__(
        self,
        fullscreen: Optional[bool] = None,
        window_size: Optional[tuple[int, int]] = None,
        data_dir: Optional[Path] = None,
        headless: bool = False,
    ):
        super().__init__(
            theme=THEME,
            fullscreen=fullscreen,
            window_size=window_size,
            headless=headless,
        )
        self.logical_size = (640, 480)
        self.surface = pygame.Surface(self.logical_size)

        self.ports: list[dict] = []
        self.index = 0
        self.tab = "all"                    # all | installed | about
        self.filter = ""
        self.modal: Optional[str] = None    # details | confirm
        self._last_load = 0.0

        pygame.display.set_caption(f"{APP_NAME} - OddHub")
        self._load()

    # -- dados --------------------------------------------------------------
    def _load(self) -> None:
        self.ports = manifest_mod.collection()
        if self.index >= len(self.ports):
            self.index = max(0, len(self.ports) - 1)

    def _visible(self) -> list[dict]:
        ports = self.ports
        if self.tab == "installed":
            ports = [port for port in ports if port.get("installed")]
        if self.filter:
            needle = self.filter.lower()
            ports = [
                port
                for port in ports
                if needle in port.get("title", "").lower() or needle in port.get("desc", "").lower()
            ]
        return ports

    def _selected(self) -> Optional[dict]:
        ports = self._visible()
        if 0 <= self.index < len(ports):
            return ports[self.index]
        return None

    def _page_count(self) -> int:
        return max(1, (len(self._visible()) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _page(self) -> int:
        return self.index // PAGE_SIZE

    # -- acoes --------------------------------------------------------------
    def _open_selected(self) -> None:
        port = self._selected()
        if not port:
            return
        if not port.get("installed"):
            self.toast_message("Este port nao esta instalado no aparelho.", "warn")
            return
        self.modal = "confirm"

    def _launch(self) -> None:
        port = self._selected()
        self.modal = None
        if not port:
            return
        script = manifest_mod.launcher_for(port)
        if not script:
            self.toast_message("Launcher do port nao encontrado.", "error")
            return
        try:
            subprocess.Popen(["/bin/sh", str(script)], cwd=str(script.parent))
            self.toast_message(f"Abrindo {port['title']}...", "ok")
        except OSError as exc:
            self.toast_message(f"Nao deu para abrir: {exc}", "error")

    def _open_search(self) -> None:
        self.keyboard.open("Buscar na colecao", self.filter, self._set_filter, max_len=60)

    def _set_filter(self, text: str) -> None:
        self.filter = text.strip()
        self.index = 0

    def _set_tab(self, tab: str) -> None:
        self.tab = tab
        self.index = 0

    # -- eventos ------------------------------------------------------------
    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue

            if self.keyboard.active:
                if self.keyboard.handle_event(event):
                    continue

            if event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_mouse(event)
            elif event.type == pygame.MOUSEWHEEL:
                self._move(-1 if event.y > 0 else 1)

    def _handle_key(self, event: pygame.event.Event) -> None:
        key = event.key
        if self.modal == "confirm":
            if key in (pygame.K_ESCAPE, pygame.K_b):
                self.modal = None
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_a):
                self._launch()
            return
        if self.modal == "details":
            if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_b):
                self.modal = None
            return

        if key in (pygame.K_ESCAPE, pygame.K_b):
            if self.filter:
                self.filter = ""
                self.index = 0
            elif self.tab != "all":
                self.tab = "all"
                self.index = 0
            else:
                self.running = False
        elif key == pygame.K_UP:
            self._move(-2)
        elif key == pygame.K_DOWN:
            self._move(2)
        elif key == pygame.K_LEFT:
            self._move(-1)
        elif key == pygame.K_RIGHT:
            self._move(1)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_a):
            self._open_selected()
        elif key == pygame.K_TAB:
            self._open_search()
        elif key == pygame.K_y:
            port = self._selected()
            if port:
                self.modal = "details"

    def _move(self, delta: int) -> None:
        total = len(self._visible())
        if not total:
            return
        self.index = (self.index + delta) % total

    def _handle_mouse(self, event: pygame.event.Event) -> None:
        action = self.hit(event.pos)
        if not action:
            return
        if action.startswith("tab:"):
            self._set_tab(action.split(":", 1)[1])
        elif action.startswith("card:"):
            index = int(action.split(":", 1)[1])
            ports = self._visible()
            if 0 <= index < len(ports):
                if index == self.index:
                    self._open_selected()
                else:
                    self.index = index
        elif action.startswith("activate:"):
            index = int(action.split(":", 1)[1])
            ports = self._visible()
            if 0 <= index < len(ports):
                self.index = index
                self._open_selected()
        elif action == "search":
            self._open_search()
        elif action == "clear_search":
            self.filter = ""
            self.index = 0
        elif action == "settings":
            self.tab = "about"
        elif action == "confirm_yes":
            self._launch()
        elif action == "confirm_no":
            self.modal = None

    # -- desenho ------------------------------------------------------------
    def draw(self) -> None:
        now = time.time()
        self.surface.fill(self.theme.bg)
        self._hits = []

        self._draw_top_bar()
        self._draw_tabs()
        self._draw_grid()
        self._draw_bottom()

        if self.modal == "details":
            self._draw_details()
        elif self.modal == "confirm":
            self._draw_confirm()

        self.keyboard.draw(self.surface, now)
        self.draw_toast(now)

    def _draw_top_bar(self) -> None:
        width, _height = self.logical_size
        pygame.draw.rect(self.surface, self.theme.header, pygame.Rect(0, 0, width, TOP_H))
        pygame.draw.rect(self.surface, self.theme.divider, pygame.Rect(0, TOP_H - 1, width, 1))

        logo = pygame.Rect(14, 10, 32, 32)
        widgets.draw_round_rect(self.surface, self.theme.accent, logo, radius=9)
        widgets.draw_text(
            self.surface, "O", logo.center, self.fonts.get(18, True), self.theme.white, anchor="center"
        )

        title_font = self.fonts.get(19, True)
        small = self.fonts.get(11)
        widgets.draw_text(self.surface, APP_NAME, (56, 8), title_font, self.theme.text)
        widgets.draw_text(
            self.surface, f"colecao de ports  ·  v{APP_VERSION}", (56, 32), small, self.theme.text_dim
        )

        self.icon_button(pygame.Rect(width - 84, 12, 30, 30), "search", "search")
        self.icon_button(pygame.Rect(width - 46, 12, 30, 30), "gear", "settings")

    def _draw_tabs(self) -> None:
        tabs = (
            ("all", "Todos"),
            ("installed", f"Instalados ({sum(1 for p in self.ports if p.get('installed'))})"),
            ("about", "Sobre"),
        )
        x = 16
        y = TABS_Y
        font = self.fonts.get(12, True)
        for tab_id, label in tabs:
            text = label
            if tab_id == "all" and self.filter:
                text = f"Todos ({len(self._visible())})"
            width = font.size(text)[0] + 26
            rect = pygame.Rect(x, y, width, TABS_H)
            active = tab_id == self.tab
            widgets.draw_round_rect(
                self.surface,
                self.theme.accent if active else self.theme.panel_2,
                rect,
                radius=16,
            )
            widgets.draw_text(
                self.surface,
                text,
                rect.center,
                font,
                self.theme.white if active else self.theme.text_dim,
                anchor="center",
            )
            if not active:
                self.add_hit(rect, f"tab:{tab_id}")
            x += width + 8

        if self.filter:
            chip_text = f"busca: {self.filter}"
            chip_w = font.size(chip_text)[0] + 34
            chip = pygame.Rect(640 - 16 - chip_w, y, chip_w, TABS_H)
            widgets.draw_round_rect(self.surface, self.theme.panel_2, chip, radius=16)
            widgets.draw_text(
                self.surface, chip_text, (chip.x + 12, chip.centery), font, self.theme.text_dim, anchor="midleft"
            )
            self.icon_button(pygame.Rect(chip.right - 24, chip.y + 6, 20, 20), "close", "clear_search")

    def _draw_grid(self) -> None:
        ports = self._visible()
        if self.tab == "about":
            self._draw_about_inline()
            return

        if not ports:
            self._draw_empty()
            return

        page = self._page()
        start = page * PAGE_SIZE
        page_ports = ports[start : start + PAGE_SIZE]

        total_w = CARD_W * 2 + GAP
        left = (self.logical_size[0] - total_w) // 2
        top = TABS_Y + TABS_H + 10

        for slot, port in enumerate(page_ports):
            col = slot % 2
            row = slot // 2
            rect = pygame.Rect(
                left + col * (CARD_W + GAP),
                top + row * (CARD_H + GAP),
                CARD_W,
                CARD_H,
            )
            self._draw_card(rect, port, start + slot)

    def _draw_card(self, rect: pygame.Rect, port: dict, index: int) -> None:
        category = port.get("category", "utility")
        color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["utility"])
        selected = index == self.index

        # sombra simples
        shadow = pygame.Rect(rect.x, rect.y + 3, rect.width, rect.height)
        widgets.draw_round_rect(self.surface, (228, 231, 236), shadow, radius=12)
        # cartao
        widgets.draw_round_rect(self.surface, self.theme.white, rect, radius=12)
        if selected:
            widgets.draw_round_rect(self.surface, self.theme.accent, rect, radius=12, width=3)
        else:
            widgets.draw_round_rect(self.surface, self.theme.divider, rect, radius=12, width=1)

        # faixa de categoria no topo
        strip = pygame.Rect(rect.x + 1, rect.y + 1, rect.width - 2, 6)
        widgets.draw_round_rect(self.surface, color, strip, radius=3)

        # icone
        tile = pygame.Rect(rect.x + 14, rect.y + 18, 44, 44)
        widgets.draw_round_rect(self.surface, color, tile, radius=10)
        widgets.draw_text(
            self.surface,
            CATEGORY_INITIALS.get(category, "?"),
            tile.center,
            self.fonts.get(20, True),
            self.theme.white,
            anchor="center",
        )

        # titulo e descricao
        title_font = self.fonts.get(15, True)
        body = self.fonts.get(11)
        text_x = rect.x + 70
        text_w = rect.width - 84
        widgets.draw_text(
            self.surface,
            widgets.truncate(title_font, port.get("title", port["id"]), text_w),
            (text_x, rect.y + 18),
            title_font,
            self.theme.text,
        )
        desc = port.get("desc", "") or "Sem descricao."
        for line_index, line in enumerate(widgets.wrap_text(body, desc, text_w, max_lines=2)):
            widgets.draw_text(
                self.surface,
                line,
                (text_x, rect.y + 40 + line_index * (body.get_height() + 2)),
                body,
                self.theme.text_dim,
            )

        # status
        installed = port.get("installed")
        pill_text = "Instalado" if installed else "Nao instalado"
        pill_font = self.fonts.get(10, True)
        pill_w = pill_font.size(pill_text)[0] + 20
        pill = pygame.Rect(rect.x + 14, rect.bottom - 40, pill_w, 22)
        widgets.draw_round_rect(
            self.surface,
            (232, 245, 238) if installed else self.theme.panel_2,
            pill,
            radius=11,
        )
        widgets.draw_text(
            self.surface,
            pill_text,
            pill.center,
            pill_font,
            self.theme.ok if installed else self.theme.text_faint,
            anchor="center",
        )

        # acao
        action_font = self.fonts.get(12, True)
        action = "Abrir" if installed else "Instalar"
        action_color = self.theme.accent if installed else self.theme.text_dim
        action_rect = pygame.Rect(rect.right - 14 - 70, rect.bottom - 40, 70, 22)
        widgets.draw_text(
            self.surface, action, (action_rect.right, action_rect.centery), action_font, action_color, anchor="midright"
        )
        self.add_hit(rect, f"card:{index}")
        self.add_hit(action_rect, f"activate:{index}")

    def _draw_empty(self) -> None:
        width, height = self.logical_size
        top = TABS_Y + TABS_H
        font = self.fonts.get(14, True)
        small = self.fonts.get(11)
        if self.filter:
            title = "Nenhum port encontrado."
            subtitle = f"Nada casa com '{self.filter}'."
        elif self.tab == "installed":
            title = "Nenhum port instalado."
            subtitle = "Instale um port da colecao pelo PortMaster."
        else:
            title = "Colecao vazia."
            subtitle = "Nenhum port cadastrado no manifesto."
        widgets.draw_text(
            self.surface, title, (width // 2, top + 60), font, self.theme.text, anchor="midtop"
        )
        widgets.draw_text(
            self.surface, subtitle, (width // 2, top + 84), small, self.theme.text_dim, anchor="midtop"
        )

    def _draw_bottom(self) -> None:
        width, height = self.logical_size
        bar = pygame.Rect(0, height - BOTTOM_H, width, BOTTOM_H)
        pygame.draw.rect(self.surface, self.theme.header, bar)
        pygame.draw.rect(self.surface, self.theme.divider, pygame.Rect(0, bar.y, width, 1))

        hint = "A: abrir · Y: detalhes · Tab: buscar · B: voltar"
        if self._page_count() > 1:
            hint = "A: abrir · Y: detalhes · Tab: buscar · <- ->: paginas"
        font = self.fonts.get(10)
        widgets.draw_text(
            self.surface,
            widgets.truncate(font, hint, width - 120),
            (16, bar.centery),
            font,
            self.theme.text_dim,
            anchor="midleft",
        )

        pages = self._page_count()
        if pages > 1:
            total_w = pages * 14
            x = width - 16 - total_w
            for page in range(pages):
                center = (x + page * 14 + 5, bar.centery)
                color = self.theme.accent if page == self._page() else self.theme.panel_3
                pygame.draw.circle(self.surface, color, center, 4)

    def _draw_about_inline(self) -> None:
        width, _height = self.logical_size
        panel = pygame.Rect(24, TABS_Y + TABS_H + 10, width - 48, 320)
        widgets.draw_round_rect(self.surface, self.theme.white, panel, radius=14)
        widgets.draw_round_rect(self.surface, self.theme.divider, panel, radius=14, width=1)

        title_font = self.fonts.get(17, True)
        body = self.fonts.get(12)
        small = self.fonts.get(11)
        y = panel.y + 18
        widgets.draw_text(self.surface, APP_NAME, (panel.x + 20, y), title_font, self.theme.text)
        y += 26
        widgets.draw_text(
            self.surface, f"versao {APP_VERSION}", (panel.x + 20, y), small, self.theme.text_dim
        )
        y += 26
        pygame.draw.rect(self.surface, self.theme.divider, pygame.Rect(panel.x + 20, y, panel.width - 40, 1))
        y += 14

        lines = [
            "Gerenciador da colecao OddHub.",
            "",
            "Lista os ports instalados no cartao e abre o escolhido.",
            "Os dados vem do manifesto que acompanha o port e dos",
            "metadados de cada app (port.json).",
            "",
            f"Pasta de ports: {manifest_mod.ports_root()}",
        ]
        for line in lines:
            for wrapped in widgets.wrap_text(body, line, panel.width - 40, max_lines=2):
                widgets.draw_text(self.surface, wrapped, (panel.x + 20, y), body, self.theme.text_dim)
                y += body.get_height() + 3
        y += 8
        widgets.draw_text(
            self.surface,
            "Feito para a colecao OddHub.",
            (panel.x + 20, panel.bottom - 22),
            small,
            self.theme.text_faint,
        )

    def _draw_details(self) -> None:
        self.modal_backdrop()
        panel = self.panel(500, 300)
        port = self._selected()
        title_font = self.fonts.get(16, True)
        body = self.fonts.get(12)
        small = self.fonts.get(11)

        widgets.draw_text(self.surface, "Detalhes", (panel.x + 18, panel.y + 14), title_font, self.theme.text)
        if port:
            category = port.get("category", "utility")
            color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["utility"])
            tile = pygame.Rect(panel.x + 18, panel.y + 44, 46, 46)
            widgets.draw_round_rect(self.surface, color, tile, radius=10)
            widgets.draw_text(
                self.surface,
                CATEGORY_INITIALS.get(category, "?"),
                tile.center,
                self.fonts.get(20, True),
                self.theme.white,
                anchor="center",
            )
            widgets.draw_text(
                self.surface,
                widgets.truncate(title_font, port.get("title", port["id"]), panel.width - 100),
                (tile.right + 14, tile.y + 2),
                title_font,
                self.theme.text,
            )
            widgets.draw_text(
                self.surface,
                port.get("id", ""),
                (tile.right + 14, tile.y + 24),
                small,
                self.theme.text_dim,
            )

            y = tile.bottom + 16
            pygame.draw.rect(self.surface, self.theme.divider, pygame.Rect(panel.x + 18, y, panel.width - 36, 1))
            y += 12
            rows = (
                ("Categoria", category),
                ("Instalado", "sim" if port.get("installed") else "nao"),
                ("Pasta", port.get("path", "") or "-"),
            )
            for label, value in rows:
                line = f"{label}: {value}"
                for wrapped in widgets.wrap_text(small, line, panel.width - 36, max_lines=3):
                    widgets.draw_text(self.surface, wrapped, (panel.x + 18, y), small, self.theme.text_dim)
                    y += small.get_height() + 3
                y += 3
            y += 6
            for wrapped in widgets.wrap_text(body, port.get("desc", ""), panel.width - 36, max_lines=4):
                widgets.draw_text(self.surface, wrapped, (panel.x + 18, y), body, self.theme.text)
                y += body.get_height() + 3

        widgets.draw_text(
            self.surface,
            "Enter ou Esc: fechar",
            (panel.centerx, panel.bottom - 16),
            small,
            self.theme.text_faint,
            anchor="midbottom",
        )

    def _draw_confirm(self) -> None:
        self.modal_backdrop()
        panel = self.panel(360, 150)
        port = self._selected()
        title_font = self.fonts.get(15, True)
        body = self.fonts.get(12)

        widgets.draw_text(
            self.surface, "Abrir este port?", (panel.x + 18, panel.y + 16), title_font, self.theme.text
        )
        name = port.get("title", "") if port else ""
        widgets.draw_text(self.surface, name, (panel.x + 18, panel.y + 42), body, self.theme.text_dim)

        yes = pygame.Rect(panel.x + 18, panel.y + 78, 150, 38)
        no = pygame.Rect(panel.x + 180, panel.y + 78, 150, 38)
        widgets.draw_round_rect(self.surface, self.theme.accent, yes, radius=8)
        widgets.draw_text(
            self.surface, "Abrir", yes.center, self.fonts.get(13, True), self.theme.white, anchor="center"
        )
        widgets.draw_round_rect(self.surface, self.theme.panel_2, no, radius=8)
        widgets.draw_text(
            self.surface, "Cancelar", no.center, self.fonts.get(13, True), self.theme.text_dim, anchor="center"
        )
        self.add_hit(yes, "confirm_yes")
        self.add_hit(no, "confirm_no")

        widgets.draw_text(
            self.surface,
            "Enter: abrir · Esc: cancelar",
            (panel.centerx, panel.bottom - 18),
            self.fonts.get(10),
            self.theme.text_faint,
            anchor="midbottom",
        )