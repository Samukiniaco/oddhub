"""Persistencia local em SQLite (contas + emails + meta)."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from .models import Account, Email

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id         TEXT PRIMARY KEY,
    email      TEXT NOT NULL DEFAULT '',
    password   TEXT NOT NULL DEFAULT '',
    imap_host  TEXT NOT NULL DEFAULT 'imap.gmail.com',
    imap_port  INTEGER NOT NULL DEFAULT 993,
    smtp_host  TEXT NOT NULL DEFAULT 'smtp.gmail.com',
    smtp_port  INTEGER NOT NULL DEFAULT 587,
    use_tls    INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS emails (
    id          TEXT PRIMARY KEY,
    account_id  TEXT NOT NULL DEFAULT '',
    folder      TEXT NOT NULL DEFAULT 'INBOX',
    subject     TEXT NOT NULL DEFAULT '',
    sender      TEXT NOT NULL DEFAULT '',
    sender_name TEXT NOT NULL DEFAULT '',
    recipients  TEXT NOT NULL DEFAULT '[]',
    body        TEXT NOT NULL DEFAULT '',
    ts          REAL NOT NULL DEFAULT 0,
    is_read     INTEGER NOT NULL DEFAULT 0,
    is_starred  INTEGER NOT NULL DEFAULT 0,
    is_draft    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_emails_folder ON emails(account_id, folder);
CREATE INDEX IF NOT EXISTS idx_emails_ts ON emails(ts);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""


def _account(row: sqlite3.Row) -> Account:
    return Account(
        id=row["id"],
        email=row["email"],
        password=row["password"],
        imap_host=row["imap_host"],
        imap_port=row["imap_port"],
        smtp_host=row["smtp_host"],
        smtp_port=row["smtp_port"],
        use_tls=bool(row["use_tls"]),
        is_default=bool(row["is_default"]),
    )


def _email(row: sqlite3.Row) -> Email:
    try:
        to = json.loads(row["recipients"] or "[]")
    except json.JSONDecodeError:
        to = []
    return Email(
        id=row["id"],
        account_id=row["account_id"],
        folder=row["folder"],
        subject=row["subject"],
        sender=row["sender"],
        sender_name=row["sender_name"],
        to=to,
        body=row["body"],
        ts=row["ts"],
        is_read=bool(row["is_read"]),
        is_starred=bool(row["is_starred"]),
        is_draft=bool(row["is_draft"]),
    )


class Store:
    """Banco local do port. Uma unica conexao, com lock para uso em thread."""

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

    def _exec(self, sql: str, params=()):
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cur

    def _all(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchall()

    def _one(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, tuple(params)).fetchone()

    # -- meta ---------------------------------------------------------------
    def meta_get(self, key: str, default: str = "") -> str:
        row = self._one("SELECT value FROM meta WHERE key = ?", (key,))
        return row["value"] if row else default

    def meta_set(self, key: str, value: str) -> None:
        self._exec(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    # -- contas -------------------------------------------------------------
    def save_account(self, account: Account) -> None:
        self._exec(
            """INSERT INTO accounts(id, email, password, imap_host, imap_port,
                   smtp_host, smtp_port, use_tls, is_default)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   email=excluded.email, password=excluded.password,
                   imap_host=excluded.imap_host, imap_port=excluded.imap_port,
                   smtp_host=excluded.smtp_host, smtp_port=excluded.smtp_port,
                   use_tls=excluded.use_tls, is_default=excluded.is_default""",
            (
                account.id,
                account.email,
                account.password,
                account.imap_host,
                account.imap_port,
                account.smtp_host,
                account.smtp_port,
                int(account.use_tls),
                int(account.is_default),
            ),
        )

    def accounts(self) -> list[Account]:
        rows = self._all("SELECT * FROM accounts ORDER BY is_default DESC, email")
        return [_account(r) for r in rows]

    def default_account(self) -> Optional[Account]:
        row = self._one("SELECT * FROM accounts WHERE is_default = 1 LIMIT 1")
        if not row:
            row = self._one("SELECT * FROM accounts LIMIT 1")
        return _account(row) if row else None

    def delete_account(self, account_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM emails WHERE account_id = ?", (account_id,))
            self._conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            self._conn.commit()

    # -- emails -------------------------------------------------------------
    def save_email(self, email: Email) -> None:
        self._exec(
            """INSERT INTO emails(id, account_id, folder, subject, sender, sender_name,
                   recipients, body, ts, is_read, is_starred, is_draft)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   folder=excluded.folder, subject=excluded.subject,
                   sender=excluded.sender, sender_name=excluded.sender_name,
                   recipients=excluded.recipients, body=excluded.body, ts=excluded.ts,
                   is_read=excluded.is_read, is_starred=excluded.is_starred,
                   is_draft=excluded.is_draft""",
            (
                email.id,
                email.account_id,
                email.folder,
                email.subject,
                email.sender,
                email.sender_name,
                json.dumps(email.to),
                email.body,
                email.ts,
                int(email.is_read),
                int(email.is_starred),
                int(email.is_draft),
            ),
        )

    def emails(
        self,
        account_id: str,
        folder: str = "INBOX",
        limit: int = 200,
        starred: Optional[bool] = None,
    ) -> list[Email]:
        sql = "SELECT * FROM emails WHERE account_id = ? AND folder = ?"
        params: list = [account_id, folder]
        if starred is not None:
            sql += " AND is_starred = ?"
            params.append(int(starred))
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        return [_email(r) for r in self._all(sql, tuple(params))]

    def email(self, email_id: str) -> Optional[Email]:
        row = self._one("SELECT * FROM emails WHERE id = ?", (email_id,))
        return _email(row) if row else None

    def search(self, account_id: str, query: str, limit: int = 60) -> list[Email]:
        q = f"%{query.strip()}%"
        rows = self._all(
            """SELECT * FROM emails WHERE account_id = ?
                   AND (subject LIKE ? OR sender LIKE ? OR body LIKE ?)
               ORDER BY ts DESC LIMIT ?""",
            (account_id, q, q, q, limit),
        )
        return [_email(r) for r in rows]

    def set_read(self, email_id: str, value: bool = True) -> None:
        self._exec("UPDATE emails SET is_read = ? WHERE id = ?", (int(value), email_id))

    def toggle_star(self, email_id: str) -> None:
        self._exec("UPDATE emails SET is_starred = NOT is_starred WHERE id = ?", (email_id,))

    def set_folder(self, email_id: str, folder: str) -> None:
        self._exec("UPDATE emails SET folder = ? WHERE id = ?", (folder, email_id))

    def delete_email(self, email_id: str) -> None:
        self._exec("DELETE FROM emails WHERE id = ?", (email_id,))

    def count(self, account_id: Optional[str] = None, folder: Optional[str] = None) -> int:
        sql = "SELECT COUNT(*) AS n FROM emails"
        params: list = []
        clauses = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if folder:
            clauses.append("folder = ?")
            params.append(folder)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        row = self._one(sql, tuple(params))
        return int(row["n"]) if row else 0

    def count_unread(self, account_id: str, folder: str = "INBOX") -> int:
        row = self._one(
            "SELECT COUNT(*) AS n FROM emails WHERE account_id = ? AND folder = ? AND is_read = 0",
            (account_id, folder),
        )
        return int(row["n"]) if row else 0

    def stats(self) -> dict:
        row = self._one("SELECT COUNT(*) AS n FROM accounts")
        return {
            "accounts": int(row["n"]) if row else 0,
            "emails": self.count(),
            "path": str(self.path),
        }
