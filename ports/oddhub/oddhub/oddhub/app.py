"""Tela do gerenciador OddHub."""

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
from .theme import THEME

TOP_H = 40
ROW_H = 52
HINT_H = 20


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
        self.scroll = 0.0
        self.modal: Optional[str] = None   # details | confirm
        self._last_load = 0.0
        pygame.display.set_caption(f"{APP_NAME} - OddHub")
        self._load()

    # -- dados --------------------------------------------------------------
    def _load(self) -> None:
        self.ports = manifest_mod.collection()
        if self.index >= len(self.ports):
            self.index = max(0, len(self.ports) - 1)
        self._last_load = time.time()

    def _selected(self) -> Optional[dict]:
        if 0 <= self.index < len(self.ports):
            return self.ports[self.index]
        return None

    # -- acoes --------------------------------------------------------------
    def _open_selected(self) -> None:
        port = self._selected()
        if not port:
            return
        if not port.get("installed"):
            self.toast_message("Este port nao esta instalado no aparelho.", "warn")
            return
        script = manifest_mod.launcher_for(port)
        if not script:
            self.toast_message("Launcher do port nao encontrado.", "error")
            return
        self.modal = "confirm"

    def _launch(self) -> None:
        port = self._selected()
        self.modal = None
        if not port:
            return
        script = manifest_mod.launcher_for(port)
        if not script:
            return
        try:
            subprocess.Popen(["/bin/sh", str(script)], cwd=str(script.parent))
            self.toast_message(f"Abrindo {port['title']}...", "ok")
        except OSError as exc:
            self.toast_message(f"Nao deu para abrir: {exc}", "error")

    # -- eventos ------------------------------------------------------------
    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_mouse(event)
            elif event.type == pygame.MOUSEWHEEL:
                self._handle_wheel(event)

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
            self.running = False
        elif key == pygame.K_UP:
            self._move(-1)
        elif key == pygame.K_DOWN:
            self._move(1)
        elif key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
            self._open_selected()
        elif key == pygame.K_TAB:
            self.modal = "details"

    def _move(self, delta: int) -> None:
        if not self.ports:
            return
        self.index = (self.index + delta) % len(self.ports)
        self._ensure_visible()

    def _handle_mouse(self, event: pygame.event.Event) -> None:
        action = self.hit(event.pos)
        if not action:
            return
        if action.startswith("port:"):
            self.index = int(action.split(":", 1)[1])
            self._ensure_visible()
        elif action == "open":
            self._open_selected()
        elif action == "details":
            self.modal = "details"
        elif action == "confirm_yes":
            self._launch()
        elif action == "confirm_no":
            self.modal = None

    def _handle_wheel(self, event: pygame.event.Event) -> None:
        self._move(-1 if event.y > 0 else 1)

    # -- layout -------------------------------------------------------------
    def _viewport(self) -> pygame.Rect:
        width, height = self.logical_size
        return pygame.Rect(0, TOP_H, width, height - TOP_H - HINT_H)

    def _max_scroll(self) -> float:
        viewport = self._viewport()
        return max(0.0, len(self.ports) * ROW_H - viewport.height)

    def _ensure_visible(self) -> None:
        viewport = self._viewport()
        top = self.index * ROW_H
        if top - self.scroll < 0:
            self.scroll = float(top)
        elif top + ROW_H - self.scroll > viewport.height:
            self.scroll = float(top + ROW_H - viewport.height)
        self.scroll = widgets.clamp(self.scroll, 0, self._max_scroll())

    # -- desenho ------------------------------------------------------------
    def draw(self) -> None:
        self.surface.fill(self.theme.bg)
        width, height = self.logical_size

        pygame.draw.rect(self.surface, self.theme.header, pygame.Rect(0, 0, width, TOP_H))
        pygame.draw.rect(self.surface, self.theme.divider, pygame.Rect(0, TOP_H - 1, width, 1))
        title_font = self.fonts.get(17, True)
        widgets.draw_text(self.surface, APP_NAME, (14, 10), title_font, self.theme.text)
        widgets.draw_text(
            self.surface,
            f"v{APP_VERSION}",
            (width - 14, 13),
            self.fonts.get(11),
            self.theme.text_faint,
            anchor="topright",
        )

        viewport = self._viewport()
        if not self.ports:
            widgets.draw_text(
                self.surface,
                "Nenhum port da colecao encontrado.",
                (viewport.centerx, viewport.y + 70),
                self.fonts.get(13),
                self.theme.text_dim,
                anchor="midtop",
            )
            widgets.draw_text(
                self.surface,
                f"Procurado em {manifest_mod.ports_root()}",
                (viewport.centerx, viewport.y + 94),
                self.fonts.get(11),
                self.theme.text_faint,
                anchor="midtop",
            )
        else:
            name_font = self.fonts.get(14, True)
            desc_font = self.fonts.get(11)
            for index, port in enumerate(self.ports):
                y = viewport.y + index * ROW_H - self.scroll
                if y + ROW_H < viewport.y or y > viewport.bottom:
                    continue
                row = pygame.Rect(0, y, width, ROW_H)
                if index == self.index:
                    pygame.draw.rect(self.surface, self.theme.select, row)
                    pygame.draw.rect(self.surface, self.theme.accent, pygame.Rect(0, y, 3, ROW_H))
                widgets.draw_text(
                    self.surface,
                    widgets.truncate(name_font, port.get("title", port["id"]), width - 110),
                    (16, y + 9),
                    name_font,
                    self.theme.text,
                )
                widgets.draw_text(
                    self.surface,
                    widgets.truncate(desc_font, port.get("desc", ""), width - 110),
                    (16, y + 28),
                    desc_font,
                    self.theme.text_dim,
                )
                state = "instalado" if port.get("installed") else "nao instalado"
                widgets.draw_text(
                    self.surface,
                    state,
                    (width - 14, y + 10),
                    desc_font,
                    self.theme.ok if port.get("installed") else self.theme.text_faint,
                    anchor="topright",
                )
                pygame.draw.rect(
                    self.surface,
                    self.theme.divider,
                    pygame.Rect(16, y + ROW_H - 1, width - 16, 1),
                )
                self.add_hit(row, f"port:{index}")

        if self.modal == "details":
            self._draw_details()
        elif self.modal == "confirm":
            self._draw_confirm()

        self.hint_bar("A: abrir · Y: detalhes · B: sair")

    def _draw_details(self) -> None:
        self.modal_backdrop()
        panel = self.panel(460, 300)
        port = self._selected()
        title_font = self.fonts.get(15, True)
        body_font = self.fonts.get(12)
        widgets.draw_text(self.surface, "Detalhes", (panel.x + 16, panel.y + 12), title_font, self.theme.text)
        if port:
            y = panel.y + 46
            body = body_font
            rows = [
                ("Titulo", port.get("title", "")),
                ("Id", port.get("id", "")),
                ("Instalado", "sim" if port.get("installed") else "nao"),
                ("Pasta", port.get("path", "") or "-"),
            ]
            for label, value in rows:
                line = f"{label}: {value}"
                for wrapped in widgets.wrap_text(body, line, panel.width - 40, max_lines=3):
                    widgets.draw_text(self.surface, wrapped, (panel.x + 16, y), body, self.theme.text_dim)
                    y += body.get_height() + 3
                y += 4
            y += 6
            pygame.draw.rect(self.surface, self.theme.divider, pygame.Rect(panel.x + 16, y, panel.width - 32, 1))
            y += 10
            for wrapped in widgets.wrap_text(body, port.get("desc", ""), panel.width - 40, max_lines=6):
                widgets.draw_text(self.surface, wrapped, (panel.x + 16, y), body, self.theme.text)
                y += body.get_height() + 3
        widgets.draw_text(
            self.surface,
            "Enter ou Esc: fechar",
            (panel.centerx, panel.bottom - 18),
            self.fonts.get(10),
            self.theme.text_faint,
            anchor="midbottom",
        )

    def _draw_confirm(self) -> None:
        self.modal_backdrop()
        panel = self.panel(340, 150)
        port = self._selected()
        name = port.get("title", "") if port else ""
        widgets.draw_text(
            self.surface, "Abrir este port?", (panel.x + 16, panel.y + 14), self.fonts.get(14, True), self.theme.text
        )
        widgets.draw_text(
            self.surface, name, (panel.x + 16, panel.y + 38), self.fonts.get(12), self.theme.text_dim
        )
        yes = pygame.Rect(panel.x + 16, panel.y + 74, 140, 30)
        no = pygame.Rect(panel.x + 170, panel.y + 74, 140, 30)
        for rect, label in ((yes, "Abrir"), (no, "Cancelar")):
            widgets.draw_round_rect(self.surface, self.theme.panel_2, rect, radius=6)
            widgets.draw_text(self.surface, label, rect.center, self.fonts.get(12), self.theme.text, anchor="center")
        self.add_hit(yes, "confirm_yes")
        self.add_hit(no, "confirm_no")
        widgets.draw_text(
            self.surface,
            "Enter: abrir · Esc: voltar",
            (panel.centerx, panel.bottom - 14),
            self.fonts.get(10),
            self.theme.text_faint,
            anchor="midbottom",
        )
