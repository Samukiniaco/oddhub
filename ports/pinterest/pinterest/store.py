"""Persistência local em SQLite (boards + pins + meta)."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from .models import Board, Pin

SCHEMA = """
CREATE TABLE IF NOT EXISTS boards (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    pin_count   INTEGER NOT NULL DEFAULT 0,
    url         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pins (
    id          TEXT PRIMARY KEY,
    board_id    TEXT NOT NULL DEFAULT '',
    title       TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    author      TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '[]',
    aspect      REAL NOT NULL DEFAULT 0.75,
    saves       INTEGER NOT NULL DEFAULT 0,
    ts          REAL NOT NULL DEFAULT 0,
    is_saved    INTEGER NOT NULL DEFAULT 0,
    image_path  TEXT NOT NULL DEFAULT '',
    seed        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pins_board ON pins(board_id);
CREATE INDEX IF NOT EXISTS idx_pins_ts ON pins(ts);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""


def _board_from_row(row: sqlite3.Row) -> Board:
    return Board(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        pin_count=row["pin_count"],
        url=row["url"],
    )


def _pin_from_row(row: sqlite3.Row) -> Pin:
    try:
        tags = json.loads(row["tags"] or "[]")
    except json.JSONDecodeError:
        tags = []
    return Pin(
        id=row["id"],
        board_id=row["board_id"],
        title=row["title"],
        description=row["description"],
        url=row["url"],
        author=row["author"],
        tags=tags,
        aspect=row["aspect"],
        saves=row["saves"],
        ts=row["ts"],
        is_saved=bool(row["is_saved"]),
        image_path=row["image_path"],
        seed=row["seed"],
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

    # -- boards -------------------------------------------------------------
    def upsert_board(self, board: Board) -> None:
        self._execute(
            """INSERT INTO boards(id, title, description, pin_count, url)
               VALUES(?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
               title=excluded.title, description=excluded.description,
               pin_count=excluded.pin_count, url=excluded.url""",
            (board.id, board.title, board.description, board.pin_count, board.url),
        )

    def get_boards(self) -> list[Board]:
        rows = self._fetchall("SELECT * FROM boards ORDER BY title COLLATE NOCASE")
        return [_board_from_row(r) for r in rows]

    def get_board(self, board_id: str) -> Optional[Board]:
        row = self._fetchone("SELECT * FROM boards WHERE id = ?", (board_id,))
        return _board_from_row(row) if row else None

    # -- pins ---------------------------------------------------------------
    def upsert_pin(self, pin: Pin) -> None:
        self._execute(
            """INSERT INTO pins(id, board_id, title, description, url, author, tags, aspect,
               saves, ts, is_saved, image_path, seed)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
               board_id=excluded.board_id, title=excluded.title, description=excluded.description,
               url=excluded.url, author=excluded.author, tags=excluded.tags, aspect=excluded.aspect,
               saves=excluded.saves, ts=excluded.ts, image_path=excluded.image_path, seed=excluded.seed""",
            (pin.id, pin.board_id, pin.title, pin.description, pin.url, pin.author,
             json.dumps(pin.tags), pin.aspect, pin.saves, pin.ts,
             int(pin.is_saved), pin.image_path, pin.seed),
        )

    def get_pins(
        self,
        board_id: Optional[str] = None,
        limit: int = 300,
        saved_only: bool = False,
    ) -> list[Pin]:
        sql = "SELECT * FROM pins"
        clauses: list[str] = []
        params: list = []
        if board_id:
            clauses.append("board_id = ?")
            params.append(board_id)
        if saved_only:
            clauses.append("is_saved = 1")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        rows = self._fetchall(sql, tuple(params))
        return [_pin_from_row(r) for r in rows]

    def get_pin(self, pin_id: str) -> Optional[Pin]:
        row = self._fetchone("SELECT * FROM pins WHERE id = ?", (pin_id,))
        return _pin_from_row(row) if row else None

    def search_pins(self, query: str, limit: int = 100) -> list[Pin]:
        q = f"%{query.strip()}%"
        rows = self._fetchall(
            """SELECT * FROM pins WHERE title LIKE ? OR description LIKE ? OR tags LIKE ?
               ORDER BY ts DESC LIMIT ?""",
            (q, q, q, limit),
        )
        return [_pin_from_row(r) for r in rows]

    def toggle_save(self, pin_id: str) -> None:
        self._execute("UPDATE pins SET is_saved = NOT is_saved WHERE id = ?", (pin_id,))

    def set_image_path(self, pin_id: str, path: str) -> None:
        self._execute("UPDATE pins SET image_path = ? WHERE id = ?", (path, pin_id))

    def clear_pins(self) -> int:
        rows = self._fetchall("SELECT id FROM pins")
        for row in rows:
            self._execute("DELETE FROM pins WHERE id = ?", (row["id"],))
        return len(rows)

    def count_pins(self, board_id: Optional[str] = None) -> int:
        if board_id:
            row = self._fetchone("SELECT COUNT(*) AS n FROM pins WHERE board_id = ?", (board_id,))
        else:
            row = self._fetchone("SELECT COUNT(*) AS n FROM pins")
        return int(row["n"]) if row else 0

    def count_boards(self) -> int:
        row = self._fetchone("SELECT COUNT(*) AS n FROM boards")
        return int(row["n"]) if row else 0

    def count_saved(self) -> int:
        row = self._fetchone("SELECT COUNT(*) AS n FROM pins WHERE is_saved = 1")
        return int(row["n"]) if row else 0

    def stats(self) -> dict:
        return {
            "boards": self.count_boards(),
            "pins": self.count_pins(),
            "saved": self.count_saved(),
            "path": str(self.path),
        }
