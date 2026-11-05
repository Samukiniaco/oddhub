"""Utilidades de desenho e texto para o pygame."""
from __future__ import annotations

import os
from typing import Optional

import pygame

from .. import config
from ..models import avatar_color, initials


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


def draw_avatar(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    name: str,
    font: pygame.font.Font,
    group: bool = False,
    ring: Optional[tuple[int, int, int]] = None,
):
    color = avatar_color(name)
    pygame.draw.circle(surface, color, center, radius)
    if ring:
        pygame.draw.circle(surface, ring, center, radius, 2)
    label = initials(name)
    draw_text(surface, label, center, font, config.WHITE, anchor="center")


def draw_badge(
    surface: pygame.Surface,
    center: tuple[int, int],
    count: int,
    font: pygame.font.Font,
):
    text = "99+" if count > 99 else str(count)
    w = max(18, font.size(text)[0] + 10)
    rect = pygame.Rect(0, 0, w, 18)
    rect.center = center
    draw_round_rect(surface, config.UNREAD, rect, radius=9)
    draw_text(surface, text, center, font, config.WHITE, anchor="center")


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
