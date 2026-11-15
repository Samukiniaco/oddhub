"""Base de todos os apps do OddHub.

Cuida da janela (640x480 logico, escalado para a tela real), do loop, dos
avisos e do clique por toque. O port herda daqui e implementa `draw`,
`update` e `handle_events`.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import pygame

from .process import is_portmaster
from .theme import Theme
from .ui import widgets
from .ui.keyboard import OnScreenKeyboard
from .ui.widgets import FontBook, Toast, draw_icon, draw_round_rect, draw_text, draw_toast


class BaseApp:
    """Esqueleto de janela e loop compartilhado."""

    LOGICAL_SIZE = (640, 480)
    FPS = 60

    def __init__(
        self,
        theme: Optional[Theme] = None,
        fullscreen: Optional[bool] = None,
        window_size: Optional[tuple[int, int]] = None,
        headless: bool = False,
    ):
        # Escala suave: nearest estouraria as fontes pequenas.
        os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "linear")

        self.theme = theme or Theme()
        widgets.set_theme(self.theme)

        self.headless = headless
        self.logical_size = self.LOGICAL_SIZE
        self.fullscreen = is_portmaster() if fullscreen is None else bool(fullscreen)

        pygame.init()
        pygame.font.init()
        self._window = self._create_window(window_size)
        self.surface = pygame.Surface(self.logical_size)
        self.fonts = FontBook()
        self.keyboard = OnScreenKeyboard(self.fonts)

        self.toast: Optional[Toast] = None
        self._hits: list[tuple[pygame.Rect, str]] = []
        self._mouse = (0, 0)
        self._clock = pygame.time.Clock()
        self.running = True

        if hasattr(pygame.key, "start_text_input"):
            try:
                pygame.key.start_text_input()
            except Exception:
                pass

    # -- janela -------------------------------------------------------------
    def _create_window(self, size: Optional[tuple[int, int]]):
        if self.fullscreen and not self.headless:
            try:
                return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            except pygame.error:
                pass
        width, height = size or self.logical_size
        try:
            return pygame.display.set_mode((width, height), pygame.RESIZABLE)
        except pygame.error:
            return pygame.display.set_mode((width, height))

    def _present(self) -> None:
        """Joga a tela logica na tela real, escalando se preciso."""
        if self.headless:
            return
        window_size = self._window.get_size()
        if window_size == self.logical_size:
            self._window.blit(self.surface, (0, 0))
        else:
            scaled = pygame.transform.smoothscale(self.surface, window_size)
            self._window.blit(scaled, (0, 0))
        pygame.display.flip()

    # -- loop ---------------------------------------------------------------
    def run(self) -> None:
        while self.running:
            dt = self._clock.tick(self.FPS) / 1000.0
            self.step(dt)
        self.shutdown()

    def step(self, dt: float = 1 / 60) -> None:
        self.handle_events()
        self.update(dt)
        self.draw()
        self._present()

    def handle_events(self) -> None:
        """As subclasses tratam os eventos."""

    def update(self, dt: float) -> None:
        """As subclasses atualizam o estado."""

    def draw(self) -> None:
        """As subclasses desenham a tela."""
        self.surface.fill(self.theme.bg)

    def shutdown(self) -> None:
        pygame.quit()

    # -- ajuda --------------------------------------------------------------
    def toast_message(self, text: str, kind: str = "info", seconds: float = 2.5) -> None:
        """Mostra um aviso temporario."""
        self.toast = Toast(text, kind, seconds, now=time.time())

    def draw_toast(self, now: float) -> None:
        if not self.toast:
            return
        draw_toast(self.surface, self.toast, self.fonts.get(12), now)
        if not self.toast.alive(now):
            self.toast = None

    def add_hit(self, rect: pygame.Rect, action: str) -> None:
        """Registra uma area clicavel."""
        self._hits.append((pygame.Rect(rect), action))

    def hit(self, pos) -> Optional[str]:
        """Devolve a acao do ultimo item clicado na posicao."""
        for rect, action in reversed(self._hits):
            if rect.collidepoint(pos):
                return action
        return None

    def icon_button(self, rect: pygame.Rect, name: str, action: str) -> None:
        """Botao de icone vetorial, com destaque ao passar o ponteiro."""
        hover = rect.collidepoint(self._mouse)
        color = self.theme.text if hover else self.theme.text_dim
        draw_icon(self.surface, rect, name, color)
        self.add_hit(rect, action)

    def hint_bar(self, text: str) -> None:
        """Barra de dica no rodape da tela."""
        width, height = self.logical_size
        bar = pygame.Rect(0, height - 20, width, 20)
        pygame.draw.rect(self.surface, self.theme.header_2, bar)
        pygame.draw.rect(self.surface, self.theme.divider, pygame.Rect(0, bar.y, width, 1))
        font = self.fonts.get(10)
        draw_text(
            self.surface,
            widgets.truncate(font, text, width - 20),
            (width // 2, bar.y + 4),
            font,
            self.theme.text_faint,
            anchor="midtop",
        )

    def modal_backdrop(self) -> None:
        """Escurece o fundo para um modal por cima."""
        dim = pygame.Surface(self.logical_size, pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        self.surface.blit(dim, (0, 0))

    def panel(self, width: int, height: int) -> pygame.Rect:
        """Retangulo centralizado de um modal."""
        sw, sh = self.logical_size
        rect = pygame.Rect(0, 0, min(width, sw - 20), min(height, sh - 20))
        rect.center = (sw // 2, sh // 2)
        draw_round_rect(self.surface, self.theme.panel, rect, radius=10)
        pygame.draw.rect(self.surface, self.theme.divider, rect, width=1, border_radius=10)
        return rect
