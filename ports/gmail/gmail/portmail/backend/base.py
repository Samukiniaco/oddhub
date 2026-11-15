"""Base dos backends do PortMail.

O `core.backend.Backend` cuida de fila de eventos e status. Aqui entra o
contrato com o store local do PortMail: contas, emails, busca e as acoes de
marcar, favoritar e apagar.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.backend import Backend as CoreBackend

from ..models import Account, Email


class MailBackend(CoreBackend):
    """Backend do PortMail sobre o store local."""

    def __init__(self, store, data_dir: Optional[Path] = None):
        super().__init__(store, data_dir)

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

    def mark_read(self, email_id: str, value: bool = True) -> None:
        self.store.set_read(email_id, value)

    def toggle_star(self, email_id: str) -> None:
        self.store.toggle_star(email_id)

    def delete_email(self, email_id: str) -> None:
        self.store.delete_email(email_id)

    def send(self, to: list[str], subject: str, body: str) -> Optional[Email]:
        raise NotImplementedError
