"""Modelos de dados para emails e contas."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Account:
    """Conta de email configurada (IMAP/SMTP)."""
    id: str
    name: str = ""
    email: str = ""
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    use_ssl: bool = True
    is_default: bool = False

    def display_name(self) -> str:
        return self.name or self.email or self.id


@dataclass
class Email:
    """Email armazenado localmente."""
    id: str
    account_id: str
    message_id: str = ""  # Message-ID header
    thread_id: str = ""
    folder: str = "INBOX"
    subject: str = ""
    sender: str = ""
    sender_name: str = ""
    recipients: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    body_text: str = ""
    body_html: str = ""
    ts: float = 0.0
    is_read: bool = False
    is_starred: bool = False
    is_important: bool = False
    is_draft: bool = False
    is_spam: bool = False
    is_trashed: bool = False
    has_attachments: bool = False
    attachment_count: int = 0
    labels: list[str] = field(default_factory=list)
    snippet: str = ""

    def display_sender(self) -> str:
        return self.sender_name or self.sender

    def display_subject(self) -> str:
        return self.subject or "(sem assunto)"


@dataclass
class BackendEvent:
    """Evento assíncrono produzido por um backend e consumido pela UI."""
    kind: str  # email | status | error | accounts | toast
    data: dict[str, Any] = field(default_factory=dict)


def format_time(ts: float) -> str:
    """Formata timestamp para exibição."""
    try:
        d = _dt.datetime.fromtimestamp(float(ts))
    except (ValueError, OSError, OverflowError):
        return ""
    now = _dt.datetime.now()
    delta = now - d
    if delta.days == 0:
        return d.strftime("%H:%M")
    elif delta.days == 1:
        return "Ontem"
    elif delta.days < 7:
        weekdays = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
        return weekdays[d.weekday()].capitalize()
    elif d.year == now.year:
        return d.strftime("%d/%m")
    else:
        return d.strftime("%d/%m/%y")


def format_full_time(ts: float) -> str:
    """Formata timestamp completo."""
    try:
        d = _dt.datetime.fromtimestamp(float(ts))
        return d.strftime("%d/%m/%Y %H:%M:%S")
    except (ValueError, OSError, OverflowError):
        return ""


def preview_text(text: str, limit: int = 120) -> str:
    """Cria preview de texto com limite de caracteres."""
    text = " ".join((text or "").split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def initials(name: str) -> str:
    """Retorna iniciais de um nome para avatar."""
    name = (name or "").strip()
    if not name:
        return "?"
    parts = [p for p in name.replace("_", " ").replace("-", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def avatar_color(email: str) -> tuple[int, int, int]:
    """Cor estável derivada do email."""
    palette = (
        (66, 133, 244),   # Google blue
        (217, 48, 37),    # Google red
        (52, 168, 83),    # Google green
        (249, 171, 0),    # Google yellow
        (171, 71, 188),   # Purple
        (0, 172, 193),    # Cyan
        (255, 112, 67),   # Deep orange
        (158, 157, 36),   # Olive
    )
    import hashlib
    digest = hashlib.sha1((email or "?").encode("utf-8", "ignore")).digest()
    return palette[digest[0] % len(palette)]


# Labels padrão do Gmail
GMAIL_LABELS = {
    "INBOX": "Caixa de entrada",
    "SENT": "Enviados",
    "DRAFT": "Rascunhos",
    "SPAM": "Spam",
    "TRASH": "Lixeira",
    "UNREAD": "Não lidos",
    "STARRED": "Estrelados",
    "IMPORTANT": "Importantes",
    "CATEGORY_PERSONAL": "Pessoal",
    "CATEGORY_SOCIAL": "Social",
    "CATEGORY_PROMOTIONS": "Promoções",
    "CATEGORY_UPDATES": "Atualizações",
    "CATEGORY_FORUM": "Fóruns",
}


def label_display(label: str) -> str:
    """Retorna nome de exibição para um label."""
    return GMAIL_LABELS.get(label, label)
