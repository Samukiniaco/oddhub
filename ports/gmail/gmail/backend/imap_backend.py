"""Backend real de email usando IMAP/SMTP (Gmail e outros provedores)."""
from __future__ import annotations

import email as email_lib
import imaplib
import logging
import smtplib
import threading
import time
import traceback
import uuid
from email.header import decode_header
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from ..models import Account, Email
from .base import Backend

log = logging.getLogger("portmail.imap")


class ImapBackend(Backend):
    id = "imap"
    label = "Email real (IMAP/SMTP)"
    real = True

    def __init__(self, store, data_dir: Optional[Path] = None):
        super().__init__(store, data_dir)
        self._imap: Optional[imaplib.IMAP4_SSL] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._last_sync: dict[str, float] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._started = True
        self.set_status("starting", "carregando conta")
        self._thread = threading.Thread(target=self._run, name="portmail-imap", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None
        self._started = False
        self.set_status("offline")

    def _run(self) -> None:
        try:
            account = self.default_account()
            if not account:
                self.set_status("error", "Nenhuma conta configurada")
                self.emit("error", text="Configure uma conta em Configurações > Contas.")
                return

            self.set_status("connecting", f"conectando a {account.imap_host}")
            self._imap = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
            self._imap.login(account.username, account.password if hasattr(account, 'password') else '')
            self.set_status("connected", account.display_name())
            self.emit("connected", account=account.id)

            # Sync inicial
            self._sync_all(account)

            # Sync periódico
            while not self._stop_evt.is_set():
                self._stop_evt.wait(60)  # sync a cada 60s
                if self._stop_evt.is_set():
                    break
                try:
                    self._sync_all(account)
                except Exception as exc:
                    log.warning("sync falhou: %s", exc)

        except Exception as exc:
            self.set_status("error", str(exc)[:240])
            self.emit("error", text=str(exc)[:240])
            log.error("falha no backend IMAP: %s", exc)
            log.debug(traceback.format_exc())
        finally:
            self._imap = None

    def _sync_all(self, account: Account) -> None:
        if not self._imap:
            return
        folders = ["INBOX", "SENT", "DRAFT", "SPAM", "TRASH"]
        for folder in folders:
            try:
                self._sync_folder(account, folder)
            except Exception as exc:
                log.debug("sync %s falhou: %s", folder, exc)

    def _sync_folder(self, account: Account, folder: str) -> None:
        if not self._imap:
            return
        self._imap.select(folder, readonly=True)
        status, data = self._imap.search(None, "ALL")
        if status != "OK":
            return
        msg_ids = data[0].split()
        # Pega apenas os últimos 100 emails
        recent = msg_ids[-100:] if len(msg_ids) > 100 else msg_ids
        
        for msg_id in recent:
            try:
                status, msg_data = self._imap.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                raw = msg_data[0][1]
                msg = email_lib.message_from_bytes(raw)
                email = self._parse_email(msg, account, folder, msg_id.decode())
                if email:
                    self.store.upsert_email(email)
                    self.emit("email", email=email, folder=folder)
            except Exception as exc:
                log.debug("parse email falhou: %s", exc)

    def _parse_email(self, msg: email_lib.message.Message, account: Account, folder: str, msg_id: str) -> Optional[Email]:
        # Extrair headers
        subject = self._decode_header(msg.get("Subject", ""))
        from_header = self._decode_header(msg.get("From", ""))
        to_header = self._decode_header(msg.get("To", ""))
        cc_header = self._decode_header(msg.get("Cc", ""))
        message_id = msg.get("Message-ID", "")
        date_str = msg.get("Date", "")
        
        # Extrair remetente
        sender_name, sender_email = self._parse_email_address(from_header)
        
        # Extrair destinatários
        recipients = [r.strip() for r in to_header.split(",") if r.strip()]
        cc = [r.strip() for r in cc_header.split(",") if r.strip()]
        
        # Extrair corpo
        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
                    except Exception:
                        pass
        else:
            try:
                body_text = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            except Exception:
                pass
        
        # Extrair timestamp
        ts = time.time()
        if date_str:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_str)
                ts = dt.timestamp()
            except Exception:
                pass
        
        # Criar email
        email = Email(
            id=f"imap:{uuid.uuid4().hex}",
            account_id=account.id,
            message_id=message_id,
            folder=folder,
            subject=subject,
            sender=sender_email,
            sender_name=sender_name,
            recipients=recipients,
            cc=cc,
            body_text=body_text,
            ts=ts,
            is_read=(folder != "INBOX" or "UNSEEN" not in str(msg.get_flags(), "")),
            snippet=body_text[:120],
        )
        return email

    def _decode_header(self, header: str) -> str:
        if not header:
            return ""
        try:
            parts = decode_header(header)
            decoded = []
            for part, charset in parts:
                if isinstance(part, bytes):
                    decoded.append(part.decode(charset or "utf-8", errors="ignore"))
                else:
                    decoded.append(part)
            return " ".join(decoded)
        except Exception:
            return header

    def _parse_email_address(self, addr: str) -> tuple[str, str]:
        """Extrai nome e email de um endereço 'Nome <email>' ou apenas email."""
        if "<" in addr and ">" in addr:
            name = addr.split("<")[0].strip().strip('"')
            email = addr.split("<")[1].split(">")[0].strip()
            return name, email
        return "", addr.strip()

    def send_email(self, to: list[str], subject: str, body: str, cc: Optional[list[str]] = None) -> Optional[Email]:
        account = self.default_account()
        if not account:
            self.emit("error", text="Nenhuma conta configurada.")
            return None
        
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = account.email
            msg["To"] = ", ".join(to)
            if cc:
                msg["Cc"] = ", ".join(cc)
            
            with smtplib.SMTP(account.smtp_host, account.smtp_port) as server:
                server.starttls()
                server.login(account.username, account.password if hasattr(account, 'password') else '')
                server.send_message(msg)
            
            # Salvar localmente
            email = Email(
                id=f"sent:{uuid.uuid4().hex}",
                account_id=account.id,
                folder="SENT",
                subject=subject,
                sender=account.email,
                sender_name=account.name,
                recipients=to,
                cc=cc or [],
                body_text=body,
                ts=time.time(),
                is_read=True,
                snippet=body[:120],
            )
            self.store.upsert_email(email)
            self.emit("email", email=email, folder="SENT")
            return email
            
        except Exception as exc:
            self.emit("error", text=f"Falha ao enviar: {exc}")
            return None

    def refresh(self, account_id: Optional[str] = None) -> None:
        if self._imap:
            try:
                account = self.default_account()
                if account:
                    self._sync_all(account)
            except Exception as exc:
                log.debug("refresh falhou: %s", exc)
