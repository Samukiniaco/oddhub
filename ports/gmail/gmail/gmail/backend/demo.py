"""Backend offline: contas e emails de exemplo para testar a interface."""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from ..models import Account, Email
from .base import Backend

DEMO_ACCOUNT = Account(
    id="demo:gmail",
    email="demo@example.com",
    password="",
    is_default=True,
)

# (remetente, nome, assunto, corpo, pastas, minutos atras, lido, starred)
_SEED = [
    ("ana@example.com", "Ana Costa", "Reuniao de amanha",
     "Oi!\n\nConfirmo a reuniao de amanha as 10h?\n\nAbraços,\nAna", "INBOX", 25, False, False),
    ("github@example.com", "GitHub", "Novos avisos de seguranca",
     "Uma dependencia sua recebeu um aviso de seguranca.\n\nRevise para a versao mais recente.",
     "INBOX", 70, False, True),
    ("loja@example.com", "Loja Exemplo", "Seu pedido foi enviado",
     "Seu pedido foi enviado e chega em ate 5 dias uteis.\n\nCodigo: 48213", "INBOX", 180, True, False),
    ("equipe@example.com", "Equipe OddHub", "Port Gmail pronto para teste",
     "O port Gmail foi reconstruido com o padrao de empacotamento do PortMaster.\n\nBom teste!",
     "INBOX", 320, True, False),
    ("news@example.com", "Newsletter", "Dicas da semana",
     "Cinco dicas de produtividade para levar no bolso:\n\n1. Uma tarefa por vez\n2. Revise pela manha\n3. Desligue notificacoes",
     "INBOX", 900, True, False),
    ("suporte@example.com", "Suporte", "Recebemos seu ticket",
     "Seu chamado foi aberto. Nosso time responde em ate 1 dia util.",
     "INBOX", 2000, True, False),
    ("vo@example.com", "Vo", "Fotos da viagem",
     "As fotos da viagem ficaram ótimas! Selectivei as melhores para o album.",
     "INBOX", 4000, True, True),
    ("bom@example.com", "Equipe de Produto", "Novidades do produto",
     "Chegou a nova versao: interface mais rapida, busca offline e tema claro.",
     "INBOX", 9000, True, False),
    ("eu@example.com", "Voce", "Teste de envio",
     "Este email foi enviado pelo proprio port, em modo demo.\n\nFuncionando.",
     "SENT", 40, True, False),
    ("eu@example.com", "Voce", "Rascunho de reuniao",
     "Pontos para discussao:\n-Orcamento\n- Cronograma\n- Responsaveis",
     "DRAFT", 120, True, False),
]


class DemoBackend(Backend):
    id = "demo"
    label = "Demo offline"
    real = False

    def __init__(self, store, data_dir: Optional[Path] = None):
        super().__init__(store, data_dir)

    def start(self) -> None:
        super().start()
        if not self.store.accounts():
            self._seed()
        self.set_status("demo", "dados locais")

    def _seed(self) -> None:
        self.store.save_account(DEMO_ACCOUNT)
        now = time.time()
        for sender, name, subject, body, folder, minutes, is_read, starred in _SEED:
            email = Email(
                id=f"demo:{uuid.uuid4().hex}",
                account_id=DEMO_ACCOUNT.id,
                folder=folder,
                subject=subject,
                sender=sender,
                sender_name=name,
                to=[DEMO_ACCOUNT.email],
                body=body,
                ts=now - minutes * 60,
                is_read=is_read,
                is_starred=starred,
            )
            self.store.save_email(email)
        self.emit("emails")

    def send(self, to: list[str], subject: str, body: str) -> Optional[Email]:
        if not to:
            return None
        email = Email(
            id=f"demo:{uuid.uuid4().hex}",
            account_id=DEMO_ACCOUNT.id,
            folder="SENT",
            subject=subject or "(sem assunto)",
            sender=DEMO_ACCOUNT.email,
            sender_name="Voce",
            to=list(to),
            body=body,
            ts=time.time(),
            is_read=True,
        )
        self.store.save_email(email)
        self.emit("emails")
        return email

    def refresh(self) -> None:
        self.set_status("demo", "dados locais")
        self.emit("emails")
