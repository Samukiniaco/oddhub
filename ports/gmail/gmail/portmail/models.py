"""Modelos de dados: conta, email e eventos do backend."""
from __future__ import annotations

import datetime as _dt
import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Account:
    """Conta IMAP/SMTP configurada pelo jogador."""
    id: str
    email: str = ""
    password: str = ""
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    is_default: bool = True

    def display(self) -> str:
        return self.email or self.id


@dataclass
class Email:
    """Email guardado localmente."""
    id: str
    account_id: str = ""
    folder: str = "INBOX"
    subject: str = ""
    sender: str = ""
    sender_name: str = ""
    to: list[str] = field(default_factory=list)
    body: str = ""
    ts: float = 0.0
    is_read: bool = False
    is_starred: bool = False
    is_draft: bool = False

    def display_sender(self) -> str:
        return self.sender_name or self.sender or "(desconhecido)"

    def display_subject(self) -> str:
        return self.subject or "(sem assunto)"

    def avatar_color(self) -> tuple[int, int, int]:
        """Cor estavel a partir do remetente."""
        palette = (
            (122, 148, 224),
            (76, 175, 120),
            (224, 168, 62),
            (211, 73, 68),
            (160, 120, 200),
            (70, 170, 190),
            (220, 130, 90),
            (140, 150, 160),
        )
        digest = hashlib.sha1((self.sender or "?").encode("utf-8", "ignore")).digest()
        return palette[digest[0] % len(palette)]


@dataclass
class BackendEvent:
    """Evento assincrono produzido pelo backend."""
    kind: str  # emails | status | error | toast
    data: dict[str, Any] = field(default_factory=dict)


def format_time(ts: float) -> str:
    """Hora curta para a lista."""
    try:
        d = _dt.datetime.fromtimestamp(float(ts))
    except (ValueError, OSError, OverflowError):
        return ""
    now = _dt.datetime.now()
    delta = now - d
    if delta.days == 0:
        return d.strftime("%H:%M")
    if delta.days == 1:
        return "Ontem"
    if delta.days < 7:
        return ("seg", "ter", "qua", "qui", "sex", "sab", "dom")[d.weekday()].capitalize()
    if d.year == now.year:
        return d.strftime("%d/%m")
    return d.strftime("%d/%m/%y")


def format_full_time(ts: float) -> str:
    """Data e hora completas para o detalhe."""
    try:
        return _dt.datetime.fromtimestamp(float(ts)).strftime("%d/%m/%Y %H:%M")
    except (ValueError, OSError, OverflowError):
        return ""


def preview(text: str, limit: int = 90) -> str:
    """Texto de uma linha para a previa."""
    text = " ".join((text or "").split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "..."
    return text


def initials(name: str) -> str:
    """Iniciais para o avatar."""
    parts = [p for p in (name or "").replace("_", " ").replace("-", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()
