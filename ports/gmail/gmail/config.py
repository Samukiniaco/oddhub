"""Configuração de caminhos, tema visual e configurações do port Gmail."""
from __future__ import annotations

import os
from pathlib import Path

APP_ID = "gmail"
APP_NAME = "PortMail"
APP_VERSION = "0.1.0"

DEFAULT_W = 960
DEFAULT_H = 600

FPS = 60

# Paleta estilo Gmail (dark mode)
BG = (32, 33, 36)
BG_CHAT = (41, 42, 45)
PANEL = (32, 33, 36)
PANEL_2 = (60, 64, 67)
HEADER = (32, 33, 36)
HEADER_2 = (48, 49, 52)
TEXT = (232, 234, 237)
TEXT_DIM = (154, 160, 166)
TEXT_FAINT = (95, 99, 104)
ACCENT = (66, 133, 244)  # Google blue
ACCENT_DARK = (52, 104, 216)
BUBBLE_IN = (60, 64, 67)
BUBBLE_OUT = (66, 133, 244)
DIVIDER = (60, 64, 67)
DANGER = (217, 48, 37)  # Google red
WARNING = (249, 171, 0)  # Google yellow
INFO = (52, 168, 83)  # Google green
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
SELECT = (50, 51, 54)
SELECT_STRONG = (66, 133, 244)
UNREAD = (66, 133, 244)

# Cores de estado do email
UNREAD_BG = (66, 133, 244)
IMPORTANT_BG = (217, 48, 37)
SENT_BG = (52, 168, 83)
DRAFT_BG = (249, 171, 0)
SPAM_BG = (150, 150, 150)

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
    """Diretório gravável de dados (sessão, emails, logs)."""
    override = os.environ.get("GMAIL_DATA")
    if override:
        base = Path(os.path.expanduser(override))
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        base = Path(appdata) / "OddHub" / "PortMail"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
        base = base / "oddhub" / "gmail"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path(__file__).resolve().parent.parent / "data"
        base.mkdir(parents=True, exist_ok=True)
    return base


def store_path() -> Path:
    return data_dir() / "emails.sqlite3"


def config_path() -> Path:
    return data_dir() / "config.json"


def log_path() -> Path:
    return data_dir() / "gmail.log"


def window_size() -> tuple[int, int]:
    try:
        w = int(os.environ.get("GMAIL_WIDTH", str(DEFAULT_W)))
        h = int(os.environ.get("GMAIL_HEIGHT", str(DEFAULT_H)))
    except (TypeError, ValueError):
        w, h = DEFAULT_W, DEFAULT_H
    return max(320, w), max(240, h)


def wants_fullscreen() -> bool:
    if os.environ.get("GMAIL_FULLSCREEN", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    if os.environ.get("GMAIL_WINDOWED", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    if os.name != "nt" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return True
    return False


def logical_size_for(actual_w: int, actual_h: int) -> tuple[int, int]:
    if actual_w <= 760 or (actual_h and actual_w / actual_h < 1.45):
        return 640, 480
    return DEFAULT_W, DEFAULT_H
