"""Monta o zip de teste de cada port, no layout que o PortMaster instala.

O zip sai no layout instalado: o script na raiz e a pasta do jogo com os
metadados dentro dela (port.json, README.md, gameinfo.xml, screenshot.png,
testing_thread.txt), que e como o harbourmaster deixa o port no aparelho.

Uso:
    python tools/build_all.py                # todos os ports
    python tools/build_all.py --port gmail   # so um
    python tools/build_all.py --out build    # outra pasta de saida
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTS = ROOT / "ports"

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
from sync_core import sync  # noqa: E402
from core import storage  # noqa: E402

METADATA = ("port.json", "README.md", "gameinfo.xml", "screenshot.png", "cover.png", "testing_thread.txt")


def port_dirs() -> list[Path]:
    """Pastas de port (as que tem port.json)."""
    out = []
    for item in sorted(PORTS.iterdir()):
        if not item.is_dir() or item.name.startswith("_"):
            continue
        if (item / "port.json").exists():
            out.append(item)
    return out


def _launcher(port_dir: Path) -> Path:
    for item in port_dir.glob("*.sh"):
        return item
    raise FileNotFoundError(f"nenhum launcher .sh em {port_dir}")


def build(port_dir: Path, out_dir: Path) -> Path:
    """Monta o zip de um port."""
    port_json = json.loads((port_dir / "port.json").read_text(encoding="utf-8"))
    name = port_json.get("name", port_dir.name + ".zip")
    game_name = port_dir.name

    sync(port_dir.name)

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        # launcher na raiz
        shutil.copy2(_launcher(port_dir), staging / _launcher(port_dir).name)
        # pasta do jogo
        game = staging / game_name
        shutil.copytree(
            port_dir / game_name,
            game,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "log.txt", "conf"),
        )
        # metadados dentro da pasta do jogo (layout instalado)
        for meta in METADATA:
            source = port_dir / meta
            if source.exists():
                shutil.copy2(source, game / meta)

        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / name
        if target.exists():
            target.unlink()
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(staging.rglob("*")):
                if item.is_file():
                    archive.write(item, item.relative_to(staging).as_posix())
    return target


def generate_manifest() -> Path:
    """Gera o manifesto da colecao que o gerenciador OddHub usa.

    Sai do registro da colecao e dos metadados de cada port, e vai junto do
    pacote do gerenciador.
    """
    registry = storage.read_json(PORTS / "registry.json", default={}) or {}
    entries = []
    for app in registry.get("apps", []):
        app_id = app.get("id", "")
        if not app_id:
            continue
        title = app.get("name", app_id)
        desc = ""
        script = ""
        port_json = PORTS / app_id / "port.json"
        if port_json.exists():
            data = storage.read_json(port_json, default={}) or {}
            attr = data.get("attr") or {}
            title = attr.get("title", title)
            desc = attr.get("desc", "")
            scripts = [item for item in (data.get("items") or []) if item.endswith(".sh")]
            script = scripts[0] if scripts else ""
        entries.append({"id": app_id, "title": title, "desc": desc, "script": script})

    dest = PORTS / "oddhub" / "oddhub" / "oddhub" / "ports.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="", help="id de um port especifico")
    parser.add_argument("--out", default=str(ROOT / "dist"), help="pasta de saida dos zips")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    targets = port_dirs()
    if args.port:
        targets = [port_dir for port_dir in targets if port_dir.name == args.port]
        if not targets:
            print(f"Port {args.port} nao encontrado em {PORTS}")
            return 1

    manifest = generate_manifest()
    print(f"manifesto da colecao: {manifest}")

    for port_dir in targets:
        try:
            target = build(port_dir, out_dir)
        except Exception as exc:
            print(f"{port_dir.name}: FALHOU ({exc})")
            continue
        size = target.stat().st_size // 1024
        print(f"{port_dir.name}: {target.name} ({size} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
