"""Configuracao do port Gmail: tema, caminhos e resolucao logica.

O port desenha sempre em 640x480 (resolucao logica) e o pygame escala para a
resolucao nativa da tela. Isso mantem o layout identico em qualquer handheld e
evita fonte minuscula em telas grandes.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_ID = "gmail"
APP_NAME = "Gmail"
APP_VERSION = "1.0.0"

# Resolucao logica (padrao dos handhelds PortMaster)
LOGICAL_W = 640
LOGICAL_H = 480

FPS = 60

# Paleta neutra de cliente de email: nao imita a identidade visual de nenhum
# servico de email e nao usa logotipo de terceiros.
BG = (18, 20, 24)
HEADER = (24, 27, 33)
HEADER_2 = (32, 36, 43)
PANEL = (28, 31, 37)
PANEL_2 = (43, 47, 56)
PANEL_3 = (55, 60, 70)
DIVIDER = (44, 48, 57)
TEXT = (233, 236, 240)
TEXT_DIM = (150, 157, 166)
TEXT_FAINT = (104, 110, 120)
ACCENT = (122, 148, 224)
ACCENT_DARK = (92, 116, 190)
SELECT = (36, 40, 48)
SELECT_STRONG = (122, 148, 224)
UNREAD = (122, 148, 224)
DANGER = (211, 73, 68)
WARNING = (224, 168, 62)
OK = (76, 175, 120)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

FOLDER_LABELS = {
    "INBOX": "Entrada",
    "SENT": "Enviados",
    "DRAFT": "Rascunhos",
    "SPAM": "Spam",
    "TRASH": "Lixeira",
}


def data_dir() -> Path:
    """Diretorio gravavel de dados (conta, emails, cache).

    No dispositivo o launcher faz bind_directories deste mesmo caminho para
    ports/gmail/gmail/conf, entao os dados ficam no cartao SD.
    """
    override = os.environ.get("GMAIL_DATA")
    if override:
        base = Path(os.path.expanduser(override))
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            base = Path(xdg)
        else:
            base = Path.home() / ".local" / "share"
        base = base / "oddhub" / "gmail"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path(__file__).resolve().parent.parent / "data"
        base.mkdir(parents=True, exist_ok=True)
    return base


def store_path() -> Path:
    return data_dir() / "mail.sqlite3"


def log_path() -> Path:
    return data_dir() / "gmail.log"


def want_fullscreen() -> bool:
    """Tela cheia por padrao no dispositivo; janela no desktop."""
    if os.environ.get("GMAIL_WINDOWED", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    if os.environ.get("GMAIL_FULLSCREEN", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    if os.name != "nt" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return True
    return False
