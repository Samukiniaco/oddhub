"""Contrato dos backends do Pinterest (demo offline e API real)."""
from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Optional

from ..models import BackendEvent, Board, Pin


class Backend:
    """Interface comum. A UI só conversa com este contrato."""

    id = "base"
    label = "Base"
    real = False

    def __init__(self, store, data_dir: Optional[Path] = None):
        self.store = store
        self.data_dir = Path(data_dir) if data_dir else None
        self._events: queue.Queue[BackendEvent] = queue.Queue()
        self._status = "offline"
        self._detail = ""
        self._lock = threading.RLock()
        self._started = False

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def tick(self, now: Optional[float] = None) -> None:
        pass

    @property
    def started(self) -> bool:
        return self._started

    # -- dados locais -------------------------------------------------------
    def boards(self) -> list[Board]:
        return self.store.get_boards()

    def pins(self, board_id: Optional[str] = None, limit: int = 300) -> list[Pin]:
        return self.store.get_pins(board_id=board_id, limit=limit)

    def pin(self, pin_id: str) -> Optional[Pin]:
        return self.store.get_pin(pin_id)

    def search(self, query: str) -> list[Pin]:
        return self.store.search_pins(query)

    def toggle_save(self, pin_id: str) -> None:
        self.store.toggle_save(pin_id)

    def set_image_path(self, pin_id: str, path: str) -> None:
        self.store.set_image_path(pin_id, path)

    # -- sincronização ------------------------------------------------------
    def refresh(self) -> None:
        pass

    def set_token(self, token: str) -> None:
        """Guarda token de API (usado pelo backend real)."""
        self.store.meta_set("api_token", token)

    def get_token(self) -> str:
        import os
        return os.environ.get("PINTEREST_TOKEN") or self.store.meta_get("api_token", "")

    # -- eventos ------------------------------------------------------------
    def emit(self, kind: str, **data) -> None:
        self._events.put(BackendEvent(kind=kind, data=data))

    def poll(self) -> list[BackendEvent]:
        out = []
        while True:
            try:
                out.append(self._events.get_nowait())
            except queue.Empty:
                break
        return out

    def set_status(self, status: str, detail: str = "") -> None:
        with self._lock:
            self._status = status
            self._detail = detail
        self.emit("status", status=status, detail=detail)

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def detail(self) -> str:
        with self._lock:
            return self._detail

    def status_label(self) -> str:
        labels = {
            "offline": "offline",
            "starting": "iniciando…",
            "connecting": "conectando…",
            "connected": "conectado",
            "syncing": "sincronizando…",
            "error": "erro",
            "demo": "modo demo",
        }
        label = labels.get(self.status, self.status)
        if self.detail:
            return f"{label} · {self.detail}"
        return label

    def info(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status_label(),
            "real": self.real,
        }
