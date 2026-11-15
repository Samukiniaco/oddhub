"""Cache em disco, para respostas JSON e imagens baixadas."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional


class DiskCache:
    """Guarda valores em arquivos, com tempo de vida opcional."""

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(key))
        return self.root / (safe[:120] + ".json")

    def _blob_path(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(key))
        return self.root / (safe[:120] + ".bin")

    def get(self, key: str, ttl: Optional[float] = None) -> Any:
        """Valor JSON guardado, ou None se sumiu ou expirou."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                obj = json.load(handle)
        except (OSError, ValueError):
            return None
        if ttl is not None and time.time() - obj.get("_ts", 0) > ttl:
            return None
        return obj.get("value")

    def set(self, key: str, value: Any) -> None:
        try:
            with open(self._path(key), "w", encoding="utf-8") as handle:
                json.dump({"_ts": time.time(), "value": value}, handle)
        except OSError:
            pass

    def get_bytes(self, key: str) -> Optional[bytes]:
        path = self._blob_path(key)
        try:
            return path.read_bytes()
        except OSError:
            return None

    def set_bytes(self, key: str, data: bytes) -> None:
        try:
            self._blob_path(key).write_bytes(data)
        except OSError:
            pass

    def remove(self, key: str) -> None:
        for path in (self._path(key), self._blob_path(key)):
            try:
                path.unlink()
            except OSError:
                pass

    def clear(self) -> None:
        """Apaga tudo o que esta no cache."""
        for path in self.root.glob("*"):
            try:
                path.unlink()
            except OSError:
                pass
