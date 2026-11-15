"""Copia o core compartilhado para dentro de um port.

O core precisa viajar com o port: no aparelho so existe a pasta do jogo, sem
o repositorio. Este script faz essa copia.

Uso:
    python tools/sync_core.py gmail            # sincroniza um port
    python tools/sync_core.py gmail oddhub     # sincroniza varios
    python tools/sync_core.py --check gmail    # so verifica se esta em dia
"""
from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def port_game_dir(app_id: str) -> Path:
    """Pasta do jogo de um port (mesmo nome do id do registro)."""
    return ROOT / "ports" / app_id / app_id


def _files(base: Path) -> list[Path]:
    return sorted(p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def sync(app_id: str) -> Path:
    """Copia o core para a pasta do jogo do port."""
    dest = port_game_dir(app_id) / "core"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(CORE, dest, ignore=IGNORE)
    return dest


def check(app_id: str) -> bool:
    """True quando a copia do core no port esta igual ao do repositorio."""
    dest = port_game_dir(app_id) / "core"
    if not dest.is_dir():
        return False
    source_files = {p.relative_to(CORE) for p in _files(CORE)}
    dest_files = {p.relative_to(dest) for p in _files(dest)}
    if source_files != dest_files:
        return False
    for relative in source_files:
        if not filecmp.cmp(CORE / relative, dest / relative, shallow=False):
            return False
    return True


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    only_check = "--check" in argv
    ids = [arg for arg in argv if not arg.startswith("--")]
    if not ids:
        print(__doc__)
        return 1
    failed = []
    for app_id in ids:
        if only_check:
            ok = check(app_id)
            print(f"{app_id}: core {'em dia' if ok else 'DIVERGENTE'}")
            if not ok:
                failed.append(app_id)
        else:
            dest = sync(app_id)
            print(f"{app_id}: core copiado para {dest}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
