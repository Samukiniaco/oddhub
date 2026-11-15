"""Cliente HTTP sobre a stdlib.

O port nao deve depender de `requests`: o runtime do PortMaster so garante a
biblioteca padrao do Python, e qualquer pacote extra vira peso no pacote ou
falta de instalacao. Aqui so existe urllib.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

USER_AGENT = "OddHub/1.0 (PortMaster port)"


class HttpError(Exception):
    """Falha de rede com o status, quando houver."""


class HttpClient:
    """HTTP simples, com repeticao de tentativa e User-Agent de port."""

    def __init__(
        self,
        timeout: float = 15.0,
        retries: int = 2,
        headers: Optional[dict] = None,
        user_agent: str = USER_AGENT,
    ):
        self.timeout = timeout
        self.retries = retries
        self.headers = {"User-Agent": user_agent, "Accept": "*/*"}
        if headers:
            self.headers.update(headers)

    def request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        headers: Optional[dict] = None,
    ) -> tuple[int, bytes]:
        """Faz a requisicao e devolve (status, corpo)."""
        last: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            request = urllib.request.Request(url, data=data, method=method)
            for key, value in self.headers.items():
                request.add_header(key, value)
            if headers:
                for key, value in headers.items():
                    request.add_header(key, value)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403, 404, 429):
                    raise HttpError(f"HTTP {exc.code} em {url}") from exc
                last = exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = exc
            if attempt < self.retries:
                time.sleep(1.0 + attempt)
        raise HttpError(f"Falha em {url}: {last}")

    def get_bytes(self, url: str, headers: Optional[dict] = None) -> bytes:
        _status, body = self.request(url, headers=headers)
        return body

    def get_text(self, url: str, headers: Optional[dict] = None) -> str:
        return self.get_bytes(url, headers=headers).decode("utf-8", "ignore")

    def get_json(self, url: str, headers: Optional[dict] = None) -> Any:
        text = self.get_text(url, headers=headers)
        try:
            return json.loads(text)
        except ValueError as exc:
            raise HttpError(f"Resposta nao e JSON: {url}") from exc

    def download(self, url: str, dest: Path, headers: Optional[dict] = None) -> Path:
        """Baixa um arquivo para o disco (imagens, por exemplo)."""
        body = self.get_bytes(url, headers=headers)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(body)
        tmp.replace(dest)
        return dest
