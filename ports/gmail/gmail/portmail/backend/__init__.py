"""Fabrica de backends do PortMail."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.backend import Backend

from .demo import DemoBackend
from .imap import ImapBackend

BACKENDS = {
    "demo": DemoBackend,
    "imap": ImapBackend,
}


def make_backend(kind: str, store, data_dir: Optional[Path] = None) -> Backend:
    """Cria o backend pedido; qualquer nome desconhecido cai no demo."""
    cls = BACKENDS.get((kind or "demo").lower(), DemoBackend)
    return cls(store, data_dir)
