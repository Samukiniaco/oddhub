"""Informacoes do processo e do aparelho.

O gptokeyb2 mata o port pelo nome do processo. Como o interpretador vem do
runtime do PortMaster e o nome dele varia (python3, python3.11...), o port
renomeia o proprio processo para um nome estavel.
"""
from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path
from typing import Optional

PR_SET_NAME = 15


def set_process_name(name: str = "oddhub") -> bool:
    """Define o nome do processo (PR_SET_NAME).

    Devolve False se nao deu, e nesse caso o launcher precisa usar outro
    alvo para o kill switch.
    """
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        return libc.prctl(PR_SET_NAME, name.encode("utf-8"), 0, 0, 0) == 0
    except Exception:
        return False


def is_portmaster() -> bool:
    """True quando o processo roda dentro do PortMaster."""
    return bool(os.environ.get("CFW_NAME") or os.environ.get("DEVICE_NAME"))


def device_info() -> dict:
    """Informacoes do aparelho fornecidas pelo PortMaster (vazio no PC)."""
    return {
        "cfw": os.environ.get("CFW_NAME", ""),
        "device": os.environ.get("DEVICE_NAME", ""),
        "arch": os.environ.get("DEVICE_ARCH", ""),
        "cpu": os.environ.get("DEVICE_CPU", ""),
        "ram": os.environ.get("DEVICE_RAM", ""),
        "width": int(os.environ.get("DISPLAY_WIDTH", "0") or 0),
        "height": int(os.environ.get("DISPLAY_HEIGHT", "0") or 0),
        "sticks": int(os.environ.get("ANALOG_STICKS", "0") or 0),
        "portmaster": is_portmaster(),
    }


def setup_logging(log_file: Optional[Path] = None, level: int = logging.INFO) -> logging.Logger:
    """Prepara o log em arquivo e no stdout."""
    logger = logging.getLogger("oddhub")
    logger.setLevel(level)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            pass
    return logger
