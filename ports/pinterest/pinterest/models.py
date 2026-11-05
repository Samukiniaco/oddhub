"""Modelos de dados para pins, boards e eventos."""
from __future__ import annotations

import datetime as _dt
import zlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Board:
    """Board (coleção) de pins."""
    id: str
    title: str = ""
    description: str = ""
    pin_count: int = 0
    url: str = ""

    def display_title(self) -> str:
        return self.title or "Sem título"


@dataclass
class Pin:
    """Pin do Pinterest."""
    id: str
    board_id: str = ""
    title: str = ""
    description: str = ""
    url: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    # proporção da miniatura (largura/altura) para o layout masonry
    aspect: float = 0.75
    saves: int = 0
    ts: float = 0.0
    is_saved: bool = False
    image_path: str = ""     # cache local de imagem (backend real)
    seed: int = 0            # seed para miniatura procedural (demo)

    def display_title(self) -> str:
        return self.title or "(sem título)"

    def color_seed(self) -> int:
        if self.seed:
            return int(self.seed)
        return zlib.crc32(self.id.encode("utf-8", "ignore"))


@dataclass
class BackendEvent:
    """Evento assíncrono produzido por um backend e consumido pela UI."""
    kind: str  # pins | board | status | error | toast | image
    data: dict[str, Any] = field(default_factory=dict)


def format_time(ts: float) -> str:
    """Formata timestamp para exibição."""
    try:
        d = _dt.datetime.fromtimestamp(float(ts))
    except (ValueError, OSError, OverflowError):
        return ""
    now = _dt.datetime.now()
    delta = now - d
    if delta.days == 0:
        return d.strftime("%H:%M")
    elif delta.days == 1:
        return "Ontem"
    elif delta.days < 7:
        weekdays = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
        return weekdays[d.weekday()].capitalize()
    elif d.year == now.year:
        return d.strftime("%d/%m")
    else:
        return d.strftime("%d/%m/%y")


def preview_text(text: str, limit: int = 120) -> str:
    """Cria preview de texto com limite de caracteres."""
    text = " ".join((text or "").split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def palette_color(seed: int) -> tuple[int, int, int]:
    """Cor estável derivada de um seed (para miniaturas e boards)."""
    palette = (
        (230, 0, 35),     # Pinterest red
        (0, 132, 187),    # blue
        (52, 168, 83),    # green
        (249, 171, 0),    # yellow
        (171, 71, 188),   # purple
        (255, 112, 67),   # deep orange
        (0, 172, 193),    # cyan
        (233, 30, 99),    # pink
        (121, 85, 72),    # brown
        (96, 125, 139),   # blue grey
    )
    return palette[(seed or 0) % len(palette)]


def board_color(board_id: str) -> tuple[int, int, int]:
    return palette_color(zlib.crc32(board_id.encode("utf-8", "ignore")))
