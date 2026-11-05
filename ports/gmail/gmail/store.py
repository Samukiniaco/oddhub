"""Persistência local em SQLite (contas + emails)."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from .models import Account, Email

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    email       TEXT NOT NULL DEFAULT '',
    imap_host   TEXT NOT NULL DEFAULT 'imap.gmail.com',
    imap_port   INTEGER NOT NULL DEFAULT 993,
    smtp_host   TEXT NOT NULL DEFAULT 'smtp.gmail.com',
    smtp_port   INTEGER NOT NULL DEFAULT 587,
    username    TEXT NOT NULL DEFAULT '',
    use_ssl     INTEGER NOT NULL DEFAULT 1,
    is_default  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS emails (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL,
    message_id      TEXT NOT NULL DEFAULT '',
    thread_id       TEXT NOT NULL DEFAULT '',
    folder          TEXT NOT NULL DEFAULT 'INBOX',
    subject         TEXT NOT NULL DEFAULT '',
    sender          TEXT NOT NULL DEFAULT '',
    sender_name     TEXT NOT NULL DEFAULT '',
    recipients      TEXT NOT NULL DEFAULT '[]',
    cc              TEXT NOT NULL DEFAULT '[]',
    bcc             TEXT NOT NULL DEFAULT '[]',
    body_text       TEXT NOT NULL DEFAULT '',
    body_html       TEXT NOT NULL DEFAULT '',
    ts              REAL NOT NULL DEFAULT 0,
    is_read         INTEGER NOT NULL DEFAULT 0,
    is_starred      INTEGER NOT NULL DEFAULT 0,
    is_important    INTEGER NOT NULL DEFAULT 0,
    is_draft        INTEGER NOT NULL DEFAULT 0,
    is_spam         INTEGER NOT NULL DEFAULT 0,
    is_trashed      INTEGER NOT NULL DEFAULT 0,
    has_attachments INTEGER NOT NULL DEFAULT 0,
    attachment_count INTEGER NOT NULL DEFAULT 0,
    labels          TEXT NOT NULL DEFAULT '[]',
    snippet         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_emails_account_folder ON emails(account_id, folder);
CREATE INDEX IF NOT EXISTS idx_emails_ts ON emails(ts);
CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(thread_id);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""


def _account_from_row(row: sqlite3.Row) -> Account:
    return Account(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        imap_host=row["imap_host"],
        imap_port=row["imap_port"],
        smtp_host=row["smtp_host"],
        smtp_port=row["smtp_port"],
        username=row["username"],
        use_ssl=bool(row["use_ssl"]),
        is_default=bool(row["is_default"]),
    )


def _email_from_row(row: sqlite3.Row) -> Email:
    try:
        recipients = json.loads(row["recipients"] or "[]")
    except json.JSONDecodeError:
        recipients = []
    try:
        cc = json.loads(row["cc"] or "[]")
    except json.JSONDecodeError:
        cc = []
    try:
        bcc = json.loads(row["bcc"] or "[]")
    except json.JSONDecodeError:
        bcc = []
    try:
        labels = json.loads(row["labels"] or "[]")
    except json.JSONDecodeError:
        labels = []
    return Email(
        id=row["id"],
        account_id=row["account_id"],
        message_id=row["message_id"],
        thread_id=row["thread_id"],
        folder=row["folder"],
        subject=row["subject"],
        sender=row["sender"],
        sender_name=row["sender_name"],
        recipients=recipients,
        cc=cc,
        bcc=bcc,
        body_text=row["body_text"],
        body_html=row["body_html"],
        ts=row["ts"],
        is_read=bool(row["is_read"]),
        is_starred=bool(row["is_starred"]),
        is_important=bool(row["is_important"]),
        is_draft=bool(row["is_draft"]),
        is_spam=bool(row["is_spam"]),
        is_trashed=bool(row["is_trashed"]),
        has_attachments=bool(row["has_attachments"]),
        attachment_count=row["attachment_count"],
        labels=labels,
        snippet=row["snippet"],
    )


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=15.0)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.commit()
                self._conn.close()
            except sqlite3.Error:
                pass

    def _execute(self, sql: str, params=()):
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cur

    def _fetchall(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchall()

    def _fetchone(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchone()

    # -- meta ---------------------------------------------------------------
    def meta_get(self, key: str, default: str = "") -> str:
        row = self._fetchone("SELECT value FROM meta WHERE key = ?", (key,))
        return row["value"] if row else default

    def meta_set(self, key: str, value: str) -> None:
        self._execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    # -- accounts -----------------------------------------------------------
    def upsert_account(self, account: Account) -> None:
        self._execute(
            """INSERT INTO accounts(id, name, email, imap_host, imap_port, smtp_host, smtp_port, username, use_ssl, is_default)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
               name=excluded.name, email=excluded.email, imap_host=excluded.imap_host,
               imap_port=excluded.imap_port, smtp_host=excluded.smtp_host, smtp_port=excluded.smtp_port,
               username=excluded.username, use_ssl=excluded.use_ssl, is_default=excluded.is_default""",
            (account.id, account.name, account.email, account.imap_host, account.imap_port,
             account.smtp_host, account.smtp_port, account.username, int(account.use_ssl), int(account.is_default)),
        )

    def get_accounts(self) -> list[Account]:
        rows = self._fetchall("SELECT * FROM accounts ORDER BY is_default DESC, name COLLATE NOCASE")
        return [_account_from_row(r) for r in rows]

    def get_account(self, account_id: str) -> Optional[Account]:
        row = self._fetchone("SELECT * FROM accounts WHERE id = ?", (account_id,))
        return _account_from_row(row) if row else None

    def get_default_account(self) -> Optional[Account]:
        row = self._fetchone("SELECT * FROM accounts WHERE is_default = 1 LIMIT 1")
        if row:
            return _account_from_row(row)
        row = self._fetchone("SELECT * FROM accounts LIMIT 1")
        return _account_from_row(row) if row else None

    def delete_account(self, account_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM emails WHERE account_id = ?", (account_id,))
            self._conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            self._conn.commit()

    # -- emails -------------------------------------------------------------
    def upsert_email(self, email: Email) -> bool:
        """Insere/atualiza um email. Retorna True se foi novo."""
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO emails(id, account_id, message_id, thread_id, folder, subject, sender, sender_name,
                   recipients, cc, bcc, body_text, body_html, ts, is_read, is_starred, is_important,
                   is_draft, is_spam, is_trashed, has_attachments, attachment_count, labels, snippet)
                   VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                   subject=excluded.subject, sender=excluded.sender, sender_name=excluded.sender_name,
                   recipients=excluded.recipients, cc=excluded.cc, bcc=excluded.bcc,
                   body_text=excluded.body_text, body_html=excluded.body_html, ts=excluded.ts,
                   is_read=excluded.is_read, is_starred=excluded.is_starred, is_important=excluded.is_important,
                   is_draft=excluded.is_draft, is_spam=excluded.is_spam, is_trashed=excluded.is_trashed,
                   has_attachments=excluded.has_attachments, attachment_count=excluded.attachment_count,
                   labels=excluded.labels, snippet=excluded.snippet""",
                (email.id, email.account_id, email.message_id, email.thread_id, email.folder,
                 email.subject, email.sender, email.sender_name, json.dumps(email.recipients),
                 json.dumps(email.cc), json.dumps(email.bcc), email.body_text, email.body_html,
                 email.ts, int(email.is_read), int(email.is_starred), int(email.is_important),
                 int(email.is_draft), int(email.is_spam), int(email.is_trashed),
                 int(email.has_attachments), email.attachment_count, json.dumps(email.labels), email.snippet),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def get_emails(self, account_id: str, folder: str = "INBOX", limit: int = 200) -> list[Email]:
        rows = self._fetchall(
            "SELECT * FROM emails WHERE account_id = ? AND folder = ? ORDER BY ts DESC LIMIT ?",
            (account_id, folder, limit),
        )
        return [_email_from_row(r) for r in rows]

    def get_email(self, email_id: str) -> Optional[Email]:
        row = self._fetchone("SELECT * FROM emails WHERE id = ?", (email_id,))
        return _email_from_row(row) if row else None

    def mark_read(self, email_id: str, is_read: bool = True) -> None:
        self._execute("UPDATE emails SET is_read = ? WHERE id = ?", (int(is_read), email_id))

    def toggle_star(self, email_id: str) -> None:
        self._execute("UPDATE emails SET is_starred = NOT is_starred WHERE id = ?", (email_id,))

    def toggle_important(self, email_id: str) -> None:
        self._execute("UPDATE emails SET is_important = NOT is_important WHERE id = ?", (email_id,))

    def move_email(self, email_id: str, folder: str) -> None:
        self._execute("UPDATE emails SET folder = ? WHERE id = ?", (folder, email_id))

    def delete_email(self, email_id: str) -> None:
        self._execute("DELETE FROM emails WHERE id = ?", (email_id,))

    def search_emails(self, account_id: str, query: str, limit: int = 50) -> list[Email]:
        q = f"%{query.strip()}%"
        rows = self._fetchall(
            """SELECT * FROM emails WHERE account_id = ? AND (subject LIKE ? OR sender LIKE ? OR body_text LIKE ?)
               ORDER BY ts DESC LIMIT ?""",
            (account_id, q, q, q, limit),
        )
        return [_email_from_row(r) for r in rows]

    def count_emails(self, account_id: Optional[str] = None, folder: Optional[str] = None) -> int:
        if account_id and folder:
            row = self._fetchone("SELECT COUNT(*) AS n FROM emails WHERE account_id = ? AND folder = ?", (account_id, folder))
        elif account_id:
            row = self._fetchone("SELECT COUNT(*) AS n FROM emails WHERE account_id = ?", (account_id,))
        else:
            row = self._fetchone("SELECT COUNT(*) AS n FROM emails")
        return int(row["n"]) if row else 0

    def count_unread(self, account_id: str, folder: str = "INBOX") -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS n FROM emails WHERE account_id = ? AND folder = ? AND is_read = 0",
            (account_id, folder),
        )
        return int(row["n"]) if row else 0

    def clear_account(self, account_id: str) -> int:
        rows = self._fetchall("SELECT id FROM emails WHERE account_id = ?", (account_id,))
        for row in rows:
            self.delete_email(row["id"])
        return len(rows)

    def stats(self) -> dict:
        accounts = self._fetchone("SELECT COUNT(*) AS n FROM accounts")
        emails = self._fetchone("SELECT COUNT(*) AS n FROM emails")
        return {
            "accounts": int(accounts["n"]) if accounts else 0,
            "emails": int(emails["n"]) if emails else 0,
            "path": str(self.path),
        }
