"""Configuração de caminhos, tema visual e configurações do port Pinterest."""
from __future__ import annotations

import os
from pathlib import Path

APP_ID = "pinterest"
APP_NAME = "Pinterest"
APP_VERSION = "0.1.0"

DEFAULT_W = 960
DEFAULT_H = 600

FPS = 60

# Paleta estilo Pinterest (dark mode + vermelho característico)
BG = (17, 17, 17)
BG_CARD = (30, 30, 30)
PANEL = (24, 24, 24)
PANEL_2 = (45, 45, 48)
HEADER = (17, 17, 17)
HEADER_2 = (35, 35, 38)
TEXT = (245, 245, 245)
TEXT_DIM = (166, 166, 172)
TEXT_FAINT = (110, 110, 116)
ACCENT = (230, 0, 35)       # Pinterest red
ACCENT_DARK = (180, 0, 27)
DIVIDER = (45, 45, 48)
DANGER = (217, 48, 37)
WARNING = (249, 171, 0)
INFO = (52, 168, 83)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
SELECT = (40, 40, 44)
SELECT_STRONG = (230, 0, 35)

# Fontes (Windows/Linux)
FONT_CANDIDATES = {
    False: (
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ),
    True: (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ),
}


def data_dir() -> Path:
    """Diretório gravável de dados (pins, cache de imagens, logs)."""
    override = os.environ.get("PINTEREST_DATA")
    if override:
        base = Path(os.path.expanduser(override))
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        base = Path(appdata) / "OddHub" / "Pinterest"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
        base = base / "oddhub" / "pinterest"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path(__file__).resolve().parent.parent / "data"
        base.mkdir(parents=True, exist_ok=True)
    return base


def store_path() -> Path:
    return data_dir() / "pins.sqlite3"


def cache_dir() -> Path:
    path = data_dir() / "cache"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def log_path() -> Path:
    return data_dir() / "pinterest.log"


def window_size() -> tuple[int, int]:
    try:
        w = int(os.environ.get("PINTEREST_WIDTH", str(DEFAULT_W)))
        h = int(os.environ.get("PINTEREST_HEIGHT", str(DEFAULT_H)))
    except (TypeError, ValueError):
        w, h = DEFAULT_W, DEFAULT_H
    return max(320, w), max(240, h)


def wants_fullscreen() -> bool:
    if os.environ.get("PINTEREST_FULLSCREEN", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    if os.environ.get("PINTEREST_WINDOWED", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    if os.name != "nt" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return True
    return False


def logical_size_for(actual_w: int, actual_h: int) -> tuple[int, int]:
    if actual_w <= 760 or (actual_h and actual_w / actual_h < 1.45):
        return 640, 480
    return DEFAULT_W, DEFAULT_H
