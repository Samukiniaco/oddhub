"""OddHub: o gerenciador da colecao.

Mostra os ports do OddHub que estao instalados no aparelho, com o titulo e a
descricao de cada um, e abre o port escolhido.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from core import storage


def ports_root() -> Path:
    """Pasta onde o PortMaster instala os ports."""
    for candidate in ("/roms/ports", "/mnt/mmc/ROMS/Ports", "/mnt/mmc/ports", "/userdata/roms/ports"):
        path = Path(candidate)
        if path.is_dir():
            return path
    return Path("/roms/ports")


def manifest_path() -> Path:
    """Manifiesto que vem junto do port (gerado na build)."""
    return Path(__file__).resolve().parent / "ports.json"


def load_manifest() -> list[dict]:
    """Ports da colecao, do manifesto que veio no pacote."""
    data = storage.read_json(manifest_path(), default=[])
    return data if isinstance(data, list) else []


def installed_ports() -> list[dict]:
    """Ports do OddHub encontrados no aparelho.

    Procura as pastas que tem port.json com o nosso marcador de colecao.
    """
    found: list[dict] = []
    root = ports_root()
    if not root.is_dir():
        return found
    for entry in sorted(root.iterdir()):
        port_json = entry / "port.json"
        if not port_json.is_file():
            continue
        data = storage.read_json(port_json, default={})
        if not isinstance(data, dict):
            continue
        attr = data.get("attr") or {}
        if not attr.get("title"):
            continue
        found.append(
            {
                "id": entry.name,
                "title": attr.get("title", entry.name),
                "desc": attr.get("desc", ""),
                "path": str(entry),
            }
        )
    return found


def launcher_for(port: dict) -> Optional[Path]:
    """Caminho do .sh que lanca o port, se existir."""
    script = port.get("script")
    if script:
        candidate = Path(port["path"]) / script
        if candidate.is_file():
            return candidate
    for candidate in sorted(Path(port["path"]).glob("*.sh")):
        return candidate
    return None


def collection() -> list[dict]:
    """Junta o manifesto da colecao com o que esta instalado no aparelho."""
    manifest = load_manifest()
    installed = {port["id"]: port for port in installed_ports()}
    out = []
    for entry in manifest:
        item = dict(entry)
        item["installed"] = entry["id"] in installed
        item["path"] = installed.get(entry["id"], {}).get("path", "")
        out.append(item)
    for port_id, port in installed.items():
        if not any(entry["id"] == port_id for entry in manifest):
            item = dict(port)
            item["installed"] = True
            out.append(item)
    return out
