"""Desenho: texto, icones, avisos e barras de rolagem.

Nada de glifos exoticos (setas, estrelas, simbolos): a fonte padrao do pygame
nao tem esses caracteres e eles virariam caixas vazias. Todos os icones aqui
sao desenhados com primitivas do pygame.
"""
from __future__ import annotations

import math
from typing import Optional

import pygame

from ..theme import Theme

_active_theme = Theme()


def set_theme(theme: Theme) -> None:
    """Define o tema usado pelas funcoes que nao recebem um."""
    global _active_theme
    _active_theme = theme


def get_theme() -> Theme:
    return _active_theme


class FontBook:
    """Cache de fontes. Usa a fonte do sistema se existir, senao a do pygame."""

    def __init__(self):
        self._path: Optional[str] = None
        for name in ("freesans", "dejavusans", "liberationsans", "arial", "segoeui"):
            try:
                found = pygame.font.match_font(name)
            except Exception:
                found = None
            if found:
                self._path = found
                break
        self._cache: dict[tuple[int, bool], pygame.font.Font] = {}

    def get(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (int(size), bool(bold))
        font = self._cache.get(key)
        if font is None:
            font = None
            if self._path:
                try:
                    font = pygame.font.Font(self._path, int(size))
                    font.set_bold(bold)
                except Exception:
                    font = None
            if font is None:
                font = pygame.font.Font(None, int(size))
                if bold:
                    font.set_bold(True)
            self._cache[key] = font
        return font


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def truncate(font: pygame.font.Font, text: str, max_width: int) -> str:
    """Corta o texto para caber na largura, com reticencias."""
    text = text or ""
    if font.size(text)[0] <= max_width:
        return text
    ell = "..."
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.size(text[:mid] + ell)[0] <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + ell


def wrap_text(font: pygame.font.Font, text: str, max_width: int, max_lines: int = 0) -> list[str]:
    """Quebra o texto em linhas que cabem na largura."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
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
        lines[-1] = truncate(font, lines[-1], max_width)
    return lines or [""]


def draw_text(
    surface: pygame.Surface,
    text: str,
    pos: tuple[int, int],
    font: pygame.font.Font,
    color,
    anchor: str = "topleft",
) -> pygame.Rect:
    image = font.render(str(text), True, color)
    rect = image.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(image, rect)
    return rect


def draw_round_rect(surface, color, rect, radius: int = 6, width: int = 0):
    rect = pygame.Rect(rect)
    try:
        pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)
    except TypeError:
        pygame.draw.rect(surface, color, rect, width=width)


def draw_scrollbar(surface, track: pygame.Rect, visible_ratio: float, offset_ratio: float):
    theme = get_theme()
    if visible_ratio >= 1.0:
        return
    draw_round_rect(surface, (40, 44, 52), track, radius=2)
    height = max(20, int(track.height * visible_ratio))
    y = track.y + int((track.height - height) * clamp(offset_ratio, 0.0, 1.0))
    draw_round_rect(surface, theme.text_faint, pygame.Rect(track.x, y, track.width, height), radius=2)


def star_points(cx: float, cy: float, r_out: float, r_in: float) -> list[tuple[float, float]]:
    """Pontos de uma estrela de cinco pontas."""
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        r = r_out if i % 2 == 0 else r_in
        points.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    return points


def draw_avatar(surface, center: tuple[int, int], radius: int, name: str, font: pygame.font.Font):
    """Avatar circular com as iniciais do nome."""
    theme = get_theme()
    from .avatars import initials

    palette = (
        (122, 148, 224),
        (76, 175, 120),
        (224, 168, 62),
        (211, 73, 68),
        (160, 120, 200),
        (70, 170, 190),
        (220, 130, 90),
        (140, 150, 160),
    )
    color = palette[sum(ord(c) for c in (name or "?")) % len(palette)]
    pygame.draw.circle(surface, color, center, radius)
    draw_text(surface, initials(name), center, font, theme.white, anchor="center")


def draw_icon(surface, rect: pygame.Rect, name: str, color) -> None:
    """Desenha um icone vetorial (nao depende de fonte)."""
    cx, cy = rect.center
    if name == "search":
        pygame.draw.circle(surface, color, (cx - 2, cy - 2), 6, 2)
        pygame.draw.line(surface, color, (cx + 3, cy + 3), (cx + 8, cy + 8), 2)
    elif name == "refresh":
        pygame.draw.arc(surface, color, pygame.Rect(cx - 8, cy - 8, 16, 16), 0.5, 5.4, 2)
        pygame.draw.line(surface, color, (cx + 4, cy - 9), (cx + 9, cy - 4), 2)
    elif name == "gear":
        for dy in (-6, 0, 6):
            pygame.draw.line(surface, color, (cx - 8, cy + dy), (cx + 8, cy + dy), 2)
            pygame.draw.circle(surface, color, (cx + (-4 if dy else 4), cy + dy), 3)
    elif name == "back":
        pygame.draw.line(surface, color, (cx + 5, cy - 7), (cx - 4, cy), 2)
        pygame.draw.line(surface, color, (cx - 4, cy), (cx + 5, cy + 7), 2)
    elif name == "star":
        pygame.draw.polygon(surface, color, star_points(cx, cy, 8, 3.4))
    elif name == "star_outline":
        pygame.draw.polygon(surface, color, star_points(cx, cy, 8, 3.4), 2)
    elif name == "trash":
        pygame.draw.rect(surface, color, pygame.Rect(cx - 5, cy - 3, 10, 9), 2)
        pygame.draw.line(surface, color, (cx - 7, cy - 5), (cx + 7, cy - 5), 2)
        pygame.draw.line(surface, color, (cx - 3, cy - 8), (cx + 3, cy - 8), 2)
    elif name == "close":
        pygame.draw.line(surface, color, (cx - 5, cy - 5), (cx + 5, cy + 5), 2)
        pygame.draw.line(surface, color, (cx + 5, cy - 5), (cx - 5, cy + 5), 2)
    elif name == "envelope":
        pygame.draw.rect(surface, color, pygame.Rect(cx - 8, cy - 6, 16, 12), 2)
        pygame.draw.line(surface, color, (cx - 8, cy - 6), (cx, cy + 1), 2)
        pygame.draw.line(surface, color, (cx + 8, cy - 6), (cx, cy + 1), 2)
    elif name == "check":
        pygame.draw.line(surface, color, (cx - 5, cy), (cx - 1, cy + 4), 2)
        pygame.draw.line(surface, color, (cx - 1, cy + 4), (cx + 6, cy - 5), 2)
    elif name == "play":
        pygame.draw.polygon(surface, color, [(cx - 4, cy - 6), (cx + 6, cy), (cx - 4, cy + 6)])
    elif name == "pause":
        pygame.draw.rect(surface, color, pygame.Rect(cx - 5, cy - 6, 3, 12))
        pygame.draw.rect(surface, color, pygame.Rect(cx + 2, cy - 6, 3, 12))


class Toast:
    """Mensagem temporaria no rodape da tela."""

    def __init__(self, text: str, kind: str = "info", seconds: float = 2.5, now: float = 0.0):
        self.text = text
        self.kind = kind
        self.until = now + seconds

    def alive(self, now: float) -> bool:
        return now < self.until


def draw_toast(surface, toast: Toast, font: pygame.font.Font, now: float):
    """Desenha o aviso temporario, se ainda estiver valendo."""
    if not toast.alive(now):
        return
    theme = get_theme()
    color = {
        "error": theme.danger,
        "warn": theme.warning,
        "ok": theme.ok,
    }.get(toast.kind, theme.accent)
    lines = wrap_text(font, toast.text, min(420, surface.get_width() - 60), max_lines=3)
    width = max(font.size(line)[0] for line in lines) + 28
    height = len(lines) * (font.get_height() + 2) + 16
    rect = pygame.Rect(0, 0, width, height)
    rect.centerx = surface.get_width() // 2
    rect.bottom = surface.get_height() - 26
    draw_round_rect(surface, (36, 40, 48), rect, radius=8)
    pygame.draw.rect(surface, color, pygame.Rect(rect.x, rect.y, 3, rect.height))
    y = rect.y + 8
    for line in lines:
        draw_text(surface, line, (rect.x + 14, y), font, theme.text)
        y += font.get_height() + 2
