"""Apresentação sem alocação por frame e medição do ritmo real (não do dt limitado)."""
import os
import sys
import time
import pygame
from . import config as C


class FrameStats:
    def __init__(self):
        self.frames = 0
        self.elapsed = 0.0
        self.fps = 0.0
        self.ms = 0.0

    def tick(self, elapsed):
        if elapsed <= 0:
            return
        self.frames += 1
        self.elapsed += elapsed
        if self.elapsed >= C.FPS_SAMPLE_SECONDS:
            self.fps = self.frames / self.elapsed
            self.ms = 1000 * self.elapsed / self.frames
            self.frames, self.elapsed = 0, 0.0


class FrameMeter:
    """Divide o frame em fases e loga a cada ~2s (ativa com CAVO_PERF=1).

    Mostra pra onde vao os ms: idle (espera do tick), ev, up, draw, pres, flip.
    """
    def __init__(self):
        self.enabled = os.environ.get("CAVO_PERF") == "1"
        self.acc = {}
        self.n = 0
        self.t = time.perf_counter()
        self.win = self.t

    def mark(self, name):
        now = time.perf_counter()
        if self.enabled:
            self.acc[name] = self.acc.get(name, 0.0) + now - self.t
        self.t = now

    def emit(self, fps, info=""):
        if not self.enabled:
            return
        now = time.perf_counter()
        self.n += 1
        if now - self.win < 2.0:
            return
        n = max(1, self.n)
        parts = " ".join(f"{k}={1000*v/n:.1f}" for k, v in self.acc.items())
        print(f"PERF fps={fps:.1f} {parts} ms | {info}", file=sys.stderr, flush=True)
        self.acc, self.n = {}, 0
        self.win = now


class Presenter:
    """Apresenta a resolução interna na área toda; geometria já respeita a proporção."""
    def __init__(self):
        self.geometry = None
        self.scaled = None

    def draw(self, screen, canvas, smooth):
        dw, dh = screen.get_size()
        cw, ch = canvas.get_size()
        size = (dw, dh)
        offset = (0, 0)
        geometry = (id(screen), dw, dh, size)
        if self.geometry != geometry:
            self.geometry = geometry
            self.scaled = pygame.Surface(size, depth=canvas)
            screen.fill((0, 0, 0))
        if size == canvas.get_size():
            image = canvas
        else:
            transform = pygame.transform.smoothscale if smooth else pygame.transform.scale
            transform(canvas, size, self.scaled)
            image = self.scaled
        screen.blit(image, offset)
