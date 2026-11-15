"""Caminhos de dados, cache e arquivo, do jeito que o PortMaster espera.

O launcher do port faz `bind_directories` do caminho XDG do app para a pasta
`conf/` dentro do port, entao os dados ficam no cartao SD e nao no armazenamento
interno do aparelho. Aqui a gente so calcula o mesmo caminho e garante que a
pasta exista.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional


def data_home() -> Path:
    """Raiz de dados do usuario (XDG_DATA_HOME)."""
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(os.path.expanduser(xdg))
    return Path.home() / ".local" / "share"


def app_data_dir(app_id: str, override: Optional[str] = None) -> Path:
    """Pasta de dados de um port.

    `override` (variavel de ambiente GMAIL_DATA, por exemplo) serve para
    testes no PC, onde nao existe PortMaster para fazer o bind.
    """
    if override:
        base = Path(os.path.expanduser(override))
    else:
        base = data_home() / "oddhub" / app_id
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path(tempfile.gettempdir()) / "oddhub" / app_id
        base.mkdir(parents=True, exist_ok=True)
    return base


def conf_dir(app_id: str) -> Path:
    """Pasta de configuracao local (dentro do port, no cartao SD)."""
    base = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "conf" / app_id
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return base


def cache_dir(app_id: str, override: Optional[str] = None) -> Path:
    """Pasta de cache (imagens baixadas, respostas HTTP)."""
    base = app_data_dir(app_id, override) / "cache"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return base


def store_path(app_id: str, filename: str = "data.sqlite3", override: Optional[str] = None) -> Path:
    """Caminho do banco local do port."""
    return app_data_dir(app_id, override) / filename


def read_json(path: Path, default: Any = None) -> Any:
    """Le JSON, devolvendo `default` em caso de arquivo ruim ou ausente."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def write_json(path: Path, data: Any) -> bool:
    """Escreve JSON de forma atomica (escreve em .tmp e renomeia)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        tmp.replace(path)
        return True
    except OSError:
        return False
