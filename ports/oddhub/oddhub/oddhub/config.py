"""Configuracao do gerenciador OddHub."""

from __future__ import annotations

import os
from pathlib import Path

from core import storage

APP_ID = "oddhub"
APP_NAME = "OddHub"
APP_VERSION = "1.0.0"

LOGICAL_W = 640
LOGICAL_H = 480


def data_dir() -> Path:
    return storage.app_data_dir(APP_ID, os.environ.get("ODDHUB_DATA"))


def fullscreen_override() -> bool | None:
    if os.environ.get("ODDHUB_WINDOWED", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    if os.environ.get("ODDHUB_FULLSCREEN", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return None
