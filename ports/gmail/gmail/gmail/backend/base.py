"""Contrato dos backends de email (demo offline e IMAP/SMTP real)."""
from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Optional

from ..models import Account, BackendEvent, Email


class Backend:
    """Interface comum. A UI so conversa com este contrato."""

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

    # -- ciclo --------------------------------------------------------------
    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def tick(self, now: Optional[float] = None) -> None:
        pass

    @property
    def started(self) -> bool:
        return self._started

    # -- contas -------------------------------------------------------------
    def accounts(self) -> list[Account]:
        return self.store.accounts()

    def default_account(self) -> Optional[Account]:
        return self.store.default_account()

    def save_account(self, account: Account) -> None:
        self.store.save_account(account)

    # -- emails -------------------------------------------------------------
    def emails(
        self,
        account_id: Optional[str] = None,
        folder: str = "INBOX",
        limit: int = 200,
    ) -> list[Email]:
        if account_id is None:
            account = self.default_account()
            if not account:
                return []
            account_id = account.id
        return self.store.emails(account_id, folder, limit)

    def email(self, email_id: str) -> Optional[Email]:
        return self.store.email(email_id)

    def search(self, account_id: str, query: str) -> list[Email]:
        return self.store.search(account_id, query)

    def send(self, to: list[str], subject: str, body: str) -> Optional[Email]:
        raise NotImplementedError

    def refresh(self) -> None:
        pass

    def mark_read(self, email_id: str, value: bool = True) -> None:
        self.store.set_read(email_id, value)

    def toggle_star(self, email_id: str) -> None:
        self.store.toggle_star(email_id)

    def delete_email(self, email_id: str) -> None:
        self.store.delete_email(email_id)

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
