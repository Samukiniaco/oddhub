"""Utilidades de desenho e texto para o pygame (Pinterest)."""
from __future__ import annotations

import os
from typing import Optional

import pygame

from .. import config
from ..models import palette_color


class FontBook:
    """Cache de fontes com fallback para a fonte padrão do pygame."""

    def __init__(self):
        self._paths: dict[bool, Optional[str]] = {}
        for bold in (False, True):
            path = None
            for candidate in config.FONT_CANDIDATES[bold]:
                if os.path.exists(candidate):
                    path = candidate
                    break
            if path is None:
                path = pygame.font.match_font("dejavusans", bold=bold)
            self._paths[bold] = path
        self._cache: dict[tuple[int, bool], pygame.font.Font] = {}

    def get(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (int(size), bool(bold))
        font = self._cache.get(key)
        if font is None:
            path = self._paths.get(bold)
            try:
                font = pygame.font.Font(path, int(size)) if path else pygame.font.Font(None, int(size))
            except Exception:
                font = pygame.font.Font(None, int(size))
            if bold and path is None:
                font.set_bold(True)
            self._cache[key] = font
        return font


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def wrap_text(font: pygame.font.Font, text: str, max_width: int, max_lines: int = 0) -> list[str]:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if paragraph == "":
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            if font.size(word)[0] > max_width:
                if current:
                    lines.append(current)
                    current = ""
                chunk = ""
                for ch in word:
                    if font.size(chunk + ch)[0] <= max_width:
                        chunk += ch
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                current = chunk
                continue
            probe = word if not current else current + " " + word
            if font.size(probe)[0] <= max_width:
                current = probe
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines and font.size(lines[-1] + "…")[0] > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip() + "…"
    return lines or [""]


def truncate(font: pygame.font.Font, text: str, max_width: int) -> str:
    text = text or ""
    if font.size(text)[0] <= max_width:
        return text
    ell = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.size(text[:mid] + ell)[0] <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + ell


def draw_text(
    surface: pygame.Surface,
    text: str,
    pos: tuple[int, int],
    font: pygame.font.Font,
    color: tuple[int, int, int],
    anchor: str = "topleft",
) -> pygame.Rect:
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(img, rect)
    return rect


def draw_round_rect(
    surface: pygame.Surface,
    color,
    rect,
    radius: int = 8,
    width: int = 0,
    border_color=None,
):
    rect = pygame.Rect(rect)
    try:
        pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)
    except TypeError:
        pygame.draw.rect(surface, color, rect, width=width)
    if border_color is not None and width == 0:
        try:
            pygame.draw.rect(surface, border_color, rect, width=1, border_radius=radius)
        except TypeError:
            pygame.draw.rect(surface, border_color, rect, width=1)


def draw_scrollbar(
    surface: pygame.Surface,
    track: pygame.Rect,
    visible_ratio: float,
    offset_ratio: float,
    color=config.TEXT_FAINT,
):
    if visible_ratio >= 1.0:
        return
    draw_round_rect(surface, (40, 40, 40), track, radius=3)
    h = max(24, int(track.height * visible_ratio))
    y = track.y + int((track.height - h) * clamp(offset_ratio, 0.0, 1.0))
    draw_round_rect(surface, color, pygame.Rect(track.x, y, track.width, h), radius=3)


def make_thumb(pin, width: int, height: int) -> pygame.Surface:
    """Gera uma miniatura procedural determinística para um pin (modo demo)."""
    import random

    width = max(8, int(width))
    height = max(8, int(height))
    surf = pygame.Surface((width, height))
    seed = pin.color_seed()
    rng = random.Random(seed)
    base = palette_color(seed)
    dark = tuple(max(0, int(c * 0.55)) for c in base)
    light = tuple(min(255, int(c * 1.25 + 40)) for c in base)

    # fundo em faixas verticais (gradiente simples)
    bands = 10
    for i in range(bands):
        t = i / max(1, bands - 1)
        col = tuple(int(dark[j] + (light[j] - dark[j]) * t) for j in range(3))
        y0 = int(height * i / bands)
        y1 = int(height * (i + 1) / bands)
        pygame.draw.rect(surf, col, pygame.Rect(0, y0, width, y1 - y0 + 1))

    # formas geométricas decorativas
    shape = seed % 4
    if shape == 0:
        r = int(min(width, height) * 0.3)
        pygame.draw.circle(surf, light, (width // 2, int(height * 0.4)), r)
        pygame.draw.circle(surf, dark, (width // 2, int(height * 0.4)), r, 3)
    elif shape == 1:
        for _ in range(6):
            rw = rng.randint(width // 6, width // 2)
            rh = rng.randint(height // 12, height // 5)
            x = rng.randint(0, max(0, width - rw))
            y = rng.randint(0, max(0, height - rh))
            col = light if rng.random() > 0.5 else dark
            pygame.draw.rect(surf, col, pygame.Rect(x, y, rw, rh), border_radius=6)
    elif shape == 2:
        pts = [
            (width // 2, int(height * 0.15)),
            (int(width * 0.85), int(height * 0.55)),
            (width // 2, int(height * 0.85)),
            (int(width * 0.15), int(height * 0.55)),
        ]
        pygame.draw.polygon(surf, light, pts)
        pygame.draw.polygon(surf, dark, pts, 3)
    else:
        for i in range(4):
            y = int(height * (0.2 + 0.18 * i))
            pygame.draw.line(surf, light, (int(width * 0.15), y), (int(width * 0.85), y), 4)

    # brilho sutil no topo
    glow = pygame.Surface((width, max(4, height // 4)), pygame.SRCALPHA)
    glow.fill((255, 255, 255, 26))
    surf.blit(glow, (0, 0))
    return surf


def star_points(cx: float, cy: float, r_out: float, r_in: float) -> list[tuple[float, float]]:
    """Pontos de uma estrela de 5 pontas (para desenhar ícones sem glifos)."""
    import math

    pts = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    return pts


class Toast:
    def __init__(self, text: str, kind: str = "info", seconds: float = 3.0):
        self.text = text
        self.kind = kind
        self.until = pygame.time.get_ticks() / 1000.0 + seconds

    def alive(self, now: float) -> bool:
        return now < self.until


def draw_toast(surface: pygame.Surface, toast: Toast, font: pygame.font.Font, now: float):
    if not toast.alive(now):
        return
    color = {
        "error": config.DANGER,
        "warn": config.WARNING,
        "ok": config.INFO,
    }.get(toast.kind, config.ACCENT)
    lines = wrap_text(font, toast.text, min(560, surface.get_width() - 80), max_lines=3)
    w = max(font.size(line)[0] for line in lines) + 32
    h = len(lines) * (font.get_height() + 2) + 18
    rect = pygame.Rect(0, 0, w, h)
    rect.centerx = surface.get_width() // 2
    rect.bottom = surface.get_height() - 18
    draw_round_rect(surface, (40, 40, 40), rect, radius=10)
    pygame.draw.rect(surface, color, pygame.Rect(rect.x, rect.y, 3, rect.height), border_radius=2)
    y = rect.y + 9
    for line in lines:
        draw_text(surface, line, (rect.x + 16, y), font, config.TEXT)
        y += font.get_height() + 2
