"""Contrato de backend: a UI fala so com isto.

Um backend traz dados de fora (protocolo, API, arquivo) e avisa a UI por
eventos. A UI nunca bloqueia esperando rede: ela consome a fila de eventos no
loop e redesenha.
"""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BackendEvent:
    """Evento assincrono produzido por um backend."""

    kind: str  # emails | pins | status | error | toast
    data: dict[str, Any] = field(default_factory=dict)


class Backend:
    """Base de todo backend. As subclasses implementam o que precisam."""

    id = "base"
    label = "Base"
    real = False

    def __init__(self, store=None, data_dir=None):
        self.store = store
        self.data_dir = data_dir
        self._events: "queue.Queue[BackendEvent]" = queue.Queue()
        self._status = "offline"
        self._detail = ""
        self._lock = threading.RLock()
        self._started = False

    # -- ciclo --------------------------------------------------------------
    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def tick(self, now: Optional[float] = None) -> None:
        """Chamado a cada quadro, para tarefas de fundo leves."""

    @property
    def started(self) -> bool:
        return self._started

    # -- eventos ------------------------------------------------------------
    def emit(self, kind: str, **data) -> None:
        self._events.put(BackendEvent(kind=kind, data=data))

    def poll(self) -> list[BackendEvent]:
        """Drena a fila de eventos."""
        out: list[BackendEvent] = []
        while True:
            try:
                out.append(self._events.get_nowait())
            except queue.Empty:
                break
        return out

    # -- status -------------------------------------------------------------
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
            "starting": "iniciando",
            "connecting": "conectando",
            "connected": "conectado",
            "syncing": "sincronizando",
            "error": "erro",
            "demo": "modo demo",
        }
        label = labels.get(self.status, self.status)
        if self.detail:
            return f"{label} ({self.detail})"
        return label
