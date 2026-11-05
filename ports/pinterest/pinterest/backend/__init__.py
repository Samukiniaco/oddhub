"""Fábrica de backends do Pinterest."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .api_backend import ApiBackend
from .base import Backend
from .demo import DemoBackend

BACKENDS = {
    "demo": DemoBackend,
    "api": ApiBackend,
}


def make_backend(kind: str, store, data_dir: Optional[Path] = None) -> Backend:
    cls = BACKENDS.get((kind or "demo").lower(), DemoBackend)
    return cls(store, data_dir)
