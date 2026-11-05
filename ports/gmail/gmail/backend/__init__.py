"""Fábrica de backends de email."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import Backend
from .demo import DemoBackend
from .imap_backend import ImapBackend

BACKENDS = {
    "demo": DemoBackend,
    "imap": ImapBackend,
}


def make_backend(kind: str, store, data_dir: Optional[Path] = None) -> Backend:
    cls = BACKENDS.get((kind or "demo").lower(), DemoBackend)
    return cls(store, data_dir)
