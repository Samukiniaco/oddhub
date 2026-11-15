"""Backend real: IMAP para leitura e SMTP para envio (stdlib do Python).

Nao existe dependencia extra: imaplib e smtplib ja vem com o interpretador.
A autenticacao usa a senha de aplicacao do jogador (ou a senha normal, em
provedores que aceitam). Nada de contornar bloqueio ou DRM.
"""
from __future__ import annotations

import email as email_lib
import imaplib
import logging
import smtplib
import ssl
import threading
import time
import traceback
import uuid
from email.header import decode_header
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

from ..models import Account, Email
from .base import MailBackend

log = logging.getLogger("gmail.imap")

FOLDERS = ["INBOX", "SENT", "DRAFT"]
MAX_PER_FOLDER = 40


class ImapBackend(MailBackend):
    id = "imap"
    label = "Conta real (IMAP/SMTP)"
    real = True

    def __init__(self, store, data_dir: Optional[Path] = None):
        super().__init__(store, data_dir)
        self._imap: Optional[imaplib.IMAP4_SSL] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # -- ciclo --------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._started = True
        self._thread = threading.Thread(target=self._run, name="gmail-imap", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._imap is not None:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None
        self._started = False
        self.set_status("offline")

    def refresh(self) -> None:
        """Refaz a sincronizacao."""
        if not (self._thread and self._thread.is_alive()):
            self.start()
            return
        self._stop.set()
        self._thread.join(timeout=2.0)
        self.start()

    def _run(self) -> None:
        try:
            account = self.default_account()
            if not account:
                self.set_status("error", "sem conta")
                self.emit("error", text="Configure uma conta em Configuracoes.")
                return
            if not account.password:
                self.set_status("error", "sem senha")
                self.emit("error", text="A conta nao tem senha salva. Configure em Configuracoes.")
                return

            self.set_status("connecting", account.imap_host)
            context = ssl.create_default_context()
            self._imap = imaplib.IMAP4_SSL(account.imap_host, account.imap_port, ssl_context=context)
            self._imap.login(account.email, account.password)
            self.set_status("connected", account.display())
            self.emit("status", account=account.id)

            while not self._stop.is_set():
                self.set_status("syncing", account.display())
                self._sync(account)
                self.set_status("connected", account.display())
                self._stop.wait(120)
        except Exception as exc:
            self.set_status("error", str(exc)[:120])
            self.emit("error", text=f"Falha ao conectar: {exc}"[:200])
            log.error("backend IMAP falhou: %s", exc)
            log.debug(traceback.format_exc())
        finally:
            self._imap = None

    # -- sincronizacao ------------------------------------------------------
    def _sync(self, account: Account) -> None:
        if self._imap is None:
            return
        for folder in FOLDERS:
            if self._stop.is_set():
                return
            try:
                self._sync_folder(account, folder)
            except Exception as exc:
                log.debug("pasta %s: %s", folder, exc)

    def _sync_folder(self, account: Account, folder: str) -> None:
        if self._imap is None:
            return
        typ, _ = self._imap.select(f'"{folder}"', readonly=True)
        if typ != "OK":
            return
        typ, data = self._imap.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return
        ids = data[0].split()
        for msg_id in ids[-MAX_PER_FOLDER:]:
            if self._stop.is_set():
                return
            try:
                typ, payload = self._imap.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])")
                if typ != "OK":
                    continue
                head = self._header_bytes(payload)
                if head is None:
                    continue
                message = email_lib.message_from_bytes(head)
                body = self._body(account, folder, msg_id.decode())
                parsed = self._parse(message, account, folder, body)
                if parsed:
                    self.store.save_email(parsed)
                    self.emit("emails")
            except Exception as exc:
                log.debug("email %s: %s", msg_id, exc)

    def _header_bytes(self, payload) -> Optional[bytes]:
        for part in payload or []:
            if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], (bytes, bytearray)):
                return bytes(part[1])
        return None

    def _body(self, account: Account, folder: str, msg_id: str) -> str:
        """Le o corpo apenas dos emails que ainda nao existem localmente."""
        if self._imap is None:
            return ""
        try:
            typ, payload = self._imap.fetch(msg_id, "(BODY.PEEK[TEXT])")
        except Exception:
            return ""
        if typ != "OK":
            return ""
        for part in payload or []:
            if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], (bytes, bytearray)):
                return self._decode(bytes(part[1]))
        return ""

    @staticmethod
    def _decode(raw: bytes) -> str:
        for charset in ("utf-8", "iso-8859-1"):
            try:
                return raw.decode(charset)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", "ignore")

    def _parse(
        self,
        message: email_lib.message.Message,
        account: Account,
        folder: str,
        body: str,
    ) -> Optional[Email]:
        subject = self._header(message.get("Subject", ""))
        name, address = self._split_address(message.get("From", ""))
        to = [addr for _n, addr in (self._split_address(v) for v in message.get("To", "").split(",")) if addr]
        ts = time.time()
        raw_date = message.get("Date")
        if raw_date:
            try:
                ts = parsedate_to_datetime(raw_date).timestamp()
            except (TypeError, ValueError):
                pass
        message_id = message.get("Message-ID", "") or uuid.uuid4().hex
        return Email(
            id=f"imap:{message_id.strip()}",
            account_id=account.id,
            folder=folder,
            subject=subject,
            sender=address,
            sender_name=name,
            to=to,
            body=body.strip(),
            ts=ts,
            is_read=folder != "INBOX",
        )

    @staticmethod
    def _header(value: str) -> str:
        if not value:
            return ""
        try:
            parts = decode_header(value)
            out = []
            for chunk, charset in parts:
                if isinstance(chunk, bytes):
                    out.append(chunk.decode(charset or "utf-8", "ignore"))
                else:
                    out.append(chunk)
            return " ".join(out)
        except Exception:
            return value

    @staticmethod
    def _split_address(value: str) -> tuple[str, str]:
        value = (value or "").strip()
        if "<" in value and ">" in value:
            name = value.split("<", 1)[0].strip().strip('"')
            address = value.split("<", 1)[1].split(">", 1)[0].strip()
            return name, address
        return "", value

    # -- envio --------------------------------------------------------------
    def send(self, to: list[str], subject: str, body: str) -> Optional[Email]:
        account = self.default_account()
        if not account:
            self.emit("error", text="Nenhuma conta configurada.")
            return None
        if not to:
            self.emit("error", text="Informe pelo menos um destinatario.")
            return None
        try:
            message = MIMEText(body or "")
            message["Subject"] = subject or "(sem assunto)"
            message["From"] = account.email
            message["To"] = ", ".join(to)
            if account.use_tls:
                server = smtplib.SMTP(account.smtp_host, account.smtp_port, timeout=30)
                server.starttls(context=ssl.create_default_context())
            else:
                server = smtplib.SMTP_SSL(account.smtp_host, account.smtp_port, timeout=30)
            try:
                server.login(account.email, account.password)
                server.send_message(message)
            finally:
                server.quit()
        except Exception as exc:
            self.emit("error", text=f"Falha ao enviar: {exc}"[:200])
            return None

        sent = Email(
            id=f"sent:{uuid.uuid4().hex}",
            account_id=account.id,
            folder="SENT",
            subject=subject or "(sem assunto)",
            sender=account.email,
            sender_name=account.display(),
            to=list(to),
            body=body or "",
            ts=time.time(),
            is_read=True,
        )
        self.store.save_email(sent)
        self.emit("emails")
        return sent
