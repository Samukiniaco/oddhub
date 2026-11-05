"""Contrato dos backends de email (demo offline e IMAP/SMTP real)."""
from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Optional

from ..models import Account, BackendEvent, Email


class Backend:
    """Interface comum. A UI só conversa com este contrato."""

    id = "base"
    label = "Base"
    real = False

    def __init__(self, store, data_dir: Optional[Path] = None):
        self.store = store
        self.data_dir = Path(data_dir) if data_dir else None
        self._events: queue.Queue[BackendEvent] = queue.Queue()
        self._active_account: Optional[str] = None
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

    # -- accounts -----------------------------------------------------------
    def accounts(self) -> list[Account]:
        return self.store.get_accounts()

    def default_account(self) -> Optional[Account]:
        return self.store.get_default_account()

    def add_account(self, account: Account) -> None:
        self.store.upsert_account(account)

    # -- emails -------------------------------------------------------------
    def emails(self, account_id: Optional[str] = None, folder: str = "INBOX", limit: int = 200) -> list[Email]:
        if account_id is None:
            acc = self.default_account()
            if not acc:
                return []
            account_id = acc.id
        return self.store.get_emails(account_id, folder, limit)

    def email(self, email_id: str) -> Optional[Email]:
        return self.store.get_email(email_id)

    def send_email(self, to: list[str], subject: str, body: str, cc: Optional[list[str]] = None) -> Optional[Email]:
        raise NotImplementedError

    def refresh(self, account_id: Optional[str] = None) -> None:
        pass

    def mark_read(self, email_id: str, is_read: bool = True) -> None:
        self.store.mark_read(email_id, is_read)

    def toggle_star(self, email_id: str) -> None:
        self.store.toggle_star(email_id)

    def toggle_important(self, email_id: str) -> None:
        self.store.toggle_important(email_id)

    def move_email(self, email_id: str, folder: str) -> None:
        self.store.move_email(email_id, folder)

    def delete_email(self, email_id: str) -> None:
        self.store.delete_email(email_id)

    # -- events -------------------------------------------------------------
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
