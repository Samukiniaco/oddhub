"""Configuracao do port {{TITLE}}."""

from __future__ import annotations

import os
from pathlib import Path

from core import storage

APP_ID = "{{ID}}"         # id no registro da colecao
APP_NAME = "{{TITLE}}"    # nome do port
APP_VERSION = "0.1.0"

LOGICAL_W = 640
LOGICAL_H = 480


def data_dir() -> Path:
    """Pasta de dados do port (no SD quando o launcher faz o bind)."""
    return storage.app_data_dir(APP_ID, os.environ.get("{{ID_UPPER}}_DATA"))


def fullscreen_override() -> bool | None:
    """Tela cheia no aparelho, janela no PC, com override por ambiente."""
    if os.environ.get("{{ID_UPPER}}_WINDOWED", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    if os.environ.get("{{ID_UPPER}}_FULLSCREEN", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return None
