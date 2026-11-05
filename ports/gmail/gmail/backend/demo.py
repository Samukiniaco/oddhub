"""Backend offline (demo) — permite usar toda a UI sem conectar no email."""
from __future__ import annotations

import random
import time
import uuid
from pathlib import Path
from typing import Optional

from ..models import Account, Email
from .base import Backend


_SEED_ACCOUNT = Account(
    id="demo:gmail",
    name="Gmail Demo",
    email="demo@gmail.com",
    is_default=True,
)

_SEED_EMAILS = [
    # (sender_name, sender, subject, body, minutes_ago, is_read, folder, labels)
    ("Google", "no-reply@google.com", "Bem-vindo ao Gmail",
     "Seu novo Gmail está pronto para uso!\n\nConfigure seu port para acessar seus emails.",
     120, False, "INBOX", ["CATEGORY_UPDATES"]),
    
    ("Ana Costa", "ana@example.com", "Reunião de amanhã",
     "Oi! Confirmo a reunião de amanhã às 10h?\n\nAbraços,\nAna",
     90, False, "INBOX", ["CATEGORY_PERSONAL"]),
    
    ("Sistema OddHub", "noreply@oddhub.dev", "Port WhatsApp concluído",
     "O port WhatsApp foi concluído com sucesso.\n\nVeja os detalhes no repositório.",
     60, True, "INBOX", ["CATEGORY_UPDATES"]),
    
    ("Ricardo Silva", "ricardo@company.com", "Relatório mensal",
     "Segue o relatório mensal em anexo.\n\nAtenciosamente,\nRicardo",
     48, True, "INBOX", ["CATEGORY_PERSONAL"]),
    
    ("YouTube", "no-reply@youtube.com", "Novas recomendações",
     "Confira as novas recomendações de vídeos para você!",
     36, True, "INBOX", ["CATEGORY_PROMOTIONS"]),
    
    ("Equipe PortTube", "team@porttube.dev", "Atualização do port",
     "Nova versão do PortTube disponível!\n\nVeja as melhorias.",
     24, True, "INBOX", ["CATEGORY_UPDATES"]),
    
    ("Pinterest", "no-reply@pinterest.com", "Novas ideias para você",
     "Descobrimos novas ideias que você pode gostar!",
     18, True, "INBOX", ["CATEGORY_PROMOTIONS"]),
    
    ("AniPort", "info@aniport.dev", "Catálogo atualizado",
     "Novos animes adicionados ao catálogo.\n\nConfira!",
     12, True, "INBOX", ["CATEGORY_UPDATES"]),
    
    ("PortMail", "no-reply@portmail.dev", "Portmail iniciado",
     "O port PortMail está pronto para uso!\n\nConfigure sua conta IMAP.",
     6, True, "INBOX", ["CATEGORY_UPDATES"]),
    
    ("Você", "demo@gmail.com", "Teste de envio",
     "Este é um email de teste enviado pelo port.\n\nFuncionando!",
     3, True, "SENT", []),
    
    ("Sistema", "system@oddhub.dev", "Backup concluído",
     "Backup de dados concluído com sucesso.\n\nNenhuma ação necessária.",
     1, True, "INBOX", ["CATEGORY_UPDATES"]),
]


class DemoBackend(Backend):
    id = "demo"
    label = "Demo offline"
    real = False

    def __init__(self, store, data_dir: Optional[Path] = None):
        super().__init__(store, data_dir)
        self._rng = random.Random(20261104)

    def start(self) -> None:
        super().start()
        if not self.store.get_accounts():
            self._seed()
        self.set_status("demo", "dados locais")

    def _seed(self) -> None:
        self.store.upsert_account(_SEED_ACCOUNT)
        now = time.time()
        for sender_name, sender, subject, body, minutes_ago, is_read, folder, labels in _SEED_EMAILS:
            ts = now - minutes_ago * 60
            email = Email(
                id=f"demo:{uuid.uuid4().hex}",
                account_id="demo:gmail",
                message_id=f"<{uuid.uuid4().hex}@demo.gmail>",
                thread_id=f"thread-{subject[:10]}",
                folder=folder,
                subject=subject,
                sender=sender,
                sender_name=sender_name,
                recipients=["demo@gmail.com"],
                body_text=body,
                ts=ts,
                is_read=is_read,
                labels=labels,
                snippet=body[:120],
            )
            self.store.upsert_email(email)
        self.emit("emails")

    def send_email(self, to: list[str], subject: str, body: str, cc: Optional[list[str]] = None) -> Optional[Email]:
        if not to:
            return None
        now = time.time()
        email = Email(
            id=f"demo:{uuid.uuid4().hex}",
            account_id="demo:gmail",
            message_id=f"<{uuid.uuid4().hex}@demo.gmail>",
            folder="SENT",
            subject=subject or "(sem assunto)",
            sender="demo@gmail.com",
            sender_name="Você",
            recipients=to,
            cc=cc or [],
            body_text=body,
            ts=now,
            is_read=True,
            snippet=body[:120],
        )
        self.store.upsert_email(email)
        self.emit("email", email=email, folder="SENT")
        return email

    def refresh(self, account_id: Optional[str] = None) -> None:
        self.emit("emails")
