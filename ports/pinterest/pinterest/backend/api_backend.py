"""Backend real do Pinterest via API v5 (Bearer token) + cache de imagens."""
from __future__ import annotations

import json
import logging
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import Board, Pin
from .base import Backend

log = logging.getLogger("pinterest.api")

API_BASE = "https://api.pinterest.com/v5"
USER_AGENT = "OddHub-Pinterest/0.1"
MAX_IMAGES = 40
IMG_TIMEOUT = 12


def _parse_ts(value: str) -> float:
    if not value:
        return time.time()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.timestamp()
    except ValueError:
        return time.time()


class ApiBackend(Backend):
    id = "api"
    label = "API real (Pinterest v5)"
    real = True

    def __init__(self, store, data_dir: Optional[Path] = None):
        super().__init__(store, data_dir)
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._syncing = False

    # -- HTTP ---------------------------------------------------------------
    def _get(self, path: str, token: str, retries: int = 2) -> Optional[dict]:
        url = f"{API_BASE}{path}"
        last_err: Optional[Exception] = None
        for _ in range(retries + 1):
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=IMG_TIMEOUT) as resp:
                    return json.loads(resp.read().decode("utf-8", "ignore"))
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
                last_err = exc
                if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403):
                    raise
                time.sleep(1.0)
        raise RuntimeError(f"GET {path} falhou: {last_err}")

    def _download_image(self, url: str, pin_id: str) -> str:
        cache = self.data_dir / "cache" if self.data_dir else None
        if cache is None:
            return ""
        cache.mkdir(parents=True, exist_ok=True)
        safe = "".join(c for c in pin_id if c.isalnum() or c in "-_")[:80]
        dest = cache / f"{safe}.img"
        if dest.exists() and dest.stat().st_size > 0:
            return str(dest)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=IMG_TIMEOUT) as resp:
            data = resp.read()
        if not data:
            return ""
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(dest)
        return str(dest)

    # -- ciclo --------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._started = True
        self._thread = threading.Thread(target=self._run, name="pinterest-api", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        self._started = False
        self.set_status("offline")

    def tick(self, now: Optional[float] = None) -> None:
        pass

    def _run(self) -> None:
        try:
            token = self.get_token()
            if not token:
                self.set_status("error", "token ausente")
                self.emit("error", text="Configure o token da API em Configurações.")
                return
            self._sync(token)
        except Exception as exc:
            self.set_status("error", str(exc)[:240])
            self.emit("error", text=str(exc)[:240])
            log.error("falha na API do Pinterest: %s", exc)
            log.debug(traceback.format_exc())

    def refresh(self) -> None:
        if self._syncing:
            return
        if not (self._thread and self._thread.is_alive()):
            self.start()
            return
        # reinicia o ciclo
        self.stop()
        self.start()

    def _sync(self, token: str) -> None:
        self._syncing = True
        try:
            self.set_status("connecting", "conectando à API")
            me = self._get("/user/me", token)
            name = (me.get("username") or me.get("first_name") or "conta") if isinstance(me, dict) else "conta"
            self.set_status("connected", str(name)[:40])
            self.emit("connected", user=str(name))

            self.set_status("syncing", "buscando boards")
            raw = self._get("/boards?page_size=25", token)
            items = raw.get("items", []) if isinstance(raw, dict) else []
            if not items:
                raw = self._get("/user/me/boards?page_size=25", token)
                items = raw.get("items", []) if isinstance(raw, dict) else []

            boards: list[Board] = []
            for it in items:
                board = Board(
                    id=str(it.get("id", "")),
                    title=str(it.get("name", "")),
                    description=str(it.get("description", "") or ""),
                    pin_count=int(it.get("pin_count") or 0),
                    url=str(it.get("url") or ""),
                )
                if board.id:
                    self.store.upsert_board(board)
                    boards.append(board)
            self.emit("boards")

            downloaded = 0
            for board in boards:
                if self._stop_evt.is_set():
                    break
                try:
                    praw = self._get(f"/boards/{board.id}/pins?page_size=25", token)
                except Exception as exc:
                    log.debug("pins do board %s falhou: %s", board.id, exc)
                    continue
                pins = praw.get("items", []) if isinstance(praw, dict) else []
                count = 0
                for it in pins:
                    pin_id = str(it.get("id", ""))
                    if not pin_id:
                        continue
                    aspect = 0.75
                    img_url = ""
                    media = it.get("media") or {}
                    images = media.get("images") or {}
                    best_px = -1
                    for key, entry in images.items():
                        if not isinstance(entry, dict):
                            continue
                        url = entry.get("url") or ""
                        if not url:
                            continue
                        try:
                            px = int("".join(c for c in key if c.isdigit()) or 0)
                        except ValueError:
                            px = 0
                        if px > best_px and px <= 800:
                            best_px = px
                            img_url = url
                        w = int(entry.get("width") or 0)
                        h = int(entry.get("height") or 0)
                        if w and h and best_px == px:
                            aspect = max(0.4, min(2.2, w / h))
                    pin = Pin(
                        id=pin_id,
                        board_id=board.id,
                        title=str(it.get("title") or ""),
                        description=str(it.get("description") or ""),
                        url=str(it.get("link") or it.get("url") or ""),
                        author=name,
                        tags=[],
                        aspect=aspect,
                        saves=int(it.get("saves") or 0) if isinstance(it.get("saves"), int) else 0,
                        ts=_parse_ts(str(it.get("created_at") or "")),
                    )
                    self.store.upsert_pin(pin)
                    count += 1
                    if img_url and downloaded < MAX_IMAGES and not self._stop_evt.is_set():
                        try:
                            path = self._download_image(img_url, pin_id)
                            if path:
                                self.store.set_image_path(pin_id, path)
                                downloaded += 1
                                self.emit("image", pin_id=pin_id, path=path)
                        except Exception as exc:
                            log.debug("download de imagem falhou: %s", exc)
                board.pin_count = board.pin_count or count
                self.store.upsert_board(board)

            self.set_status("connected", f"{self.store.count_pins()} pins")
            self.emit("pins")
        finally:
            self._syncing = False
