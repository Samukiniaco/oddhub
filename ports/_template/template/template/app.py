"""Tela do port {{TITLE}}.

Esqueleto funcional: mostra o nome do port, a versao e o aparelho. Troque o
conteudo de `draw` pela tela do seu app.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import pygame

from core.app import BaseApp
from core.process import device_info
from core.ui import widgets

from . import config
from .theme import THEME


class {{CLASS}}(BaseApp):
    """Esqueleto de tela sobre o BaseApp do core."""

    def __init__(
        self,
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
        self._started = time.time()
        pygame.display.set_caption(f"{config.APP_NAME} - OddHub")

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False

    def draw(self) -> None:
        self.surface.fill(self.theme.bg)
        width, height = self.logical_size

        title_font = self.fonts.get(22, True)
        body_font = self.fonts.get(13)

        widgets.draw_text(self.surface, config.APP_NAME, (24, 40), title_font, self.theme.text)
        widgets.draw_text(
            self.surface, f"versao {config.APP_VERSION}", (24, 76), body_font, self.theme.text_dim
        )

        info = device_info()
        lines = [
            f"id: {config.APP_ID}",
            f"portmaster: {'sim' if info['portmaster'] else 'nao'}",
            f"aparelho: {info['device'] or '-'} ({info['arch'] or '-'})",
            f"tela: {info['width']}x{info['height']}",
            f"dados: {self.data_dir}",
        ]
        y = 120
        for line in lines:
            widgets.draw_text(self.surface, line, (24, y), body_font, self.theme.text_dim)
            y += 22

        pygame.draw.rect(
            self.surface,
            self.theme.divider,
            pygame.Rect(24, y + 8, width - 48, 1),
        )
        widgets.draw_text(
            self.surface,
            "Implemente a tela do port em app.py.",
            (24, y + 24),
            body_font,
            self.theme.text_faint,
        )

        self.hint_bar("Esc: sair · Select+Start: sair pelo PortMaster")
