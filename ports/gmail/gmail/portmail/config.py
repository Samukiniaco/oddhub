"""Configuracao do PortMail: identidade, pastas e modo de operacao."""
from __future__ import annotations

import os
from pathlib import Path

from core import storage

APP_ID = "gmail"          # id no registry da colecao
APP_NAME = "PortMail"     # nome do port
APP_VERSION = "1.0.0"

LOGICAL_W = 640
LOGICAL_H = 480

FOLDER_LABELS = {
    "INBOX": "Entrada",
    "SENT": "Enviados",
    "DRAFT": "Rascunhos",
    "SPAM": "Spam",
    "TRASH": "Lixeira",
}

FOLDERS = ("INBOX", "SENT", "DRAFT")


def data_dir() -> Path:
    """Pasta de dados do port (no SD quando o launcher faz o bind)."""
    return storage.app_data_dir(APP_ID, os.environ.get("GMAIL_DATA"))


def store_path() -> Path:
    return data_dir() / "mail.sqlite3"


def fullscreen_override() -> bool | None:
    """Tela cheia no aparelho, janela no PC, com override por ambiente.

    Devolve None quando nao ha opiniao, e ai quem decide e o BaseApp.
    """
    if os.environ.get("GMAIL_WINDOWED", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    if os.environ.get("GMAIL_FULLSCREEN", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return None
