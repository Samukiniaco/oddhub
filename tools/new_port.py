"""Cria um port novo a partir de ports/_template.

Uso:
    python tools/new_port.py <id> "Titulo do Port" [--package nome] [--genre other] [--desc "..."]

O id e o nome da pasta do port e o id no registro da colecao. O titulo e o nome
que aparece no PortMaster. O script gerado tem o mesmo nome do titulo, e o
pacote python dentro do port pode ter outro nome (ex.: id gmail, pacote
portmail).
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "ports" / "_template"
PORTS = ROOT / "ports"
REGISTRY = PORTS / "registry.json"

GENRE_TITLES = {
    "action": "Action",
    "adventure": "Adventure",
    "arcade": "Arcade",
    "casino/card": "Card",
    "fps": "FPS",
    "platformer": "Platformer",
    "puzzle": "Puzzle",
    "racing": "Racing",
    "rhythm": "Rhythm",
    "rpg": "RPG",
    "simulation": "Simulation",
    "sports": "Sports",
    "strategy": "Strategy",
    "visual novel": "Visual Novel",
    "other": "Other",
}

METADATA = ("port.json", "README.md", "gameinfo.xml", "testing_thread.txt")


def render(text: str, values: dict) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def write(path: Path, text: str) -> None:
    """Escreve sempre com LF (CRLF quebra o bash no aparelho)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def copy_tree(source: Path, dest: Path, values: dict) -> None:
    for item in source.iterdir():
        target = dest / item.name
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            copy_tree(item, target, values)
        else:
            write(target, render(item.read_text(encoding="utf-8"), values))


def register(app_id: str, title: str, desc: str) -> None:
    """Inclui o port novo no registro da colecao."""
    if not REGISTRY.exists():
        return
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    apps = data.setdefault("apps", [])
    if any(app.get("id") == app_id for app in apps):
        return
    priority = max((int(app.get("priority", 0)) for app in apps), default=0) + 1
    apps.append(
        {
            "id": app_id,
            "name": title,
            "type": "app",
            "approach": "protocolo/api",
            "status": "planejado",
            "priority": priority,
        }
    )
    apps.sort(key=lambda app: int(app.get("priority", 0)), reverse=True)
    REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("id", help="id do port (pasta e registro)")
    parser.add_argument("title", help="titulo mostrado no PortMaster")
    parser.add_argument("--package", default="", help="nome do pacote python (padrao: o id)")
    parser.add_argument("--genre", default="other", choices=sorted(GENRE_TITLES))
    parser.add_argument("--desc", default="", help="descricao curta do port")
    parser.add_argument("--no-register", action="store_true", help="nao mexe no registro")
    args = parser.parse_args(argv)

    app_id = re.sub(r"[^a-z0-9]+", "-", args.id.lower()).strip("-")
    title = args.title
    package = args.package or app_id.replace("-", "_")
    script = f"{title}.sh"
    class_name = re.sub(r"[^A-Za-z0-9]+", "", title) + "App"
    desc = args.desc or f"Port {title} para PortMaster."
    values = {
        "ID": app_id,
        "ID_UPPER": app_id.upper().replace("-", "_"),
        "TITLE": title,
        "SCRIPT": script,
        "PACKAGE": package,
        "CLASS": class_name,
        "GENRE": args.genre,
        "GENRE_TITLE": GENRE_TITLES.get(args.genre, "Other"),
        "DESC": desc,
        "DATE": datetime.date.today().strftime("%Y%m%d"),
        "URL": "https://github.com/Samukiniaco/oddhub",
    }

    dest = PORTS / app_id
    if dest.exists():
        print(f"O port {app_id} ja existe em {dest}")
        return 1
    dest.mkdir(parents=True)

    # metadados do port (layout de PR: do lado do .sh)
    for name in METADATA:
        write(dest / name, render((TEMPLATE / name).read_text(encoding="utf-8"), values))

    # launcher
    write(dest / script, render((TEMPLATE / "template.sh").read_text(encoding="utf-8"), values))

    # pasta do jogo (o core entra depois, com tools/sync_core.py)
    game = dest / app_id
    copy_tree(TEMPLATE / "template", game, values)
    (game / "template.ini").rename(game / f"{app_id}.ini")
    (game / "template").rename(game / package)
    (game / "licenses" / "LICENSE-template.txt").rename(game / "licenses" / f"LICENSE-{app_id}.txt")

    if not args.no_register:
        register(app_id, title, desc)

    print(f"Port criado em {dest}")
    print(f"  script:      {script}")
    print(f"  pasta jogo:  {app_id}/")
    print(f"  pacote:      {app_id}/{package}/")
    print(f"  proximo:     python tools/sync_core.py {app_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
