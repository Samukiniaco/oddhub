"""Scaffolding de um novo port.

Uso:
  python tools/new_port.py <id> <NomeExibido> [--genre action]

Cria ports/<id>/ com estrutura mínima e metadados PortMaster.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTS = os.path.join(ROOT, "ports")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("title")
    ap.add_argument("--genre", default="action")
    args = ap.parse_args()

    pid = args.id.lower()
    pdir = os.path.join(PORTS, pid)
    os.makedirs(pdir, exist_ok=True)
    os.makedirs(os.path.join(pdir, pid), exist_ok=True)
    os.makedirs(os.path.join(pdir, "portmaster"), exist_ok=True)

    # service.py
    service_path = os.path.join(pdir, pid, "service.py")
    if not os.path.exists(service_path):
        with open(service_path, "w", encoding="utf-8") as f:
            f.write('''"""Serviço do app {title}."""
from core.scrape.base import BaseService, Item


class Service(BaseService):
    id = "{pid}"
    name = "{title}"

    def fetch_home(self):
        # TODO: implementar busca de dados (API oficial ou scraping)
        return [Item(id="1", title="Exemplo", subtitle="placeholder")]

    def search(self, query):
        return []

    def open(self, item):
        return {{"item": item}}
'''.format(title=args.title, pid=pid))

    # main.py
    main_path = os.path.join(pdir, pid, "main.py")
    if not os.path.exists(main_path):
        with open(main_path, "w", encoding="utf-8") as f:
            f.write('''"""Entry point do port {title}."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# core vendored esperado em ./core ; fallback para raiz do repo
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.isdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "core")):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
elif os.path.isdir(os.path.join(root, "core")):
    sys.path.insert(0, root)

from core.platform.storage import game_dir


def main():
    print("Port {title} iniciado. Implemente a UI sobre core.")


if __name__ == "__main__":
    main()
'''.format(title=args.title))

    # port.json
    import json
    portjson = os.path.join(pdir, "portmaster", "port.json")
    if not os.path.exists(portjson):
        with open(portjson, "w", encoding="utf-8") as f:
            json.dump({
                "version": 2,
                "name": pid + ".zip",
                "items": [args.title.replace(" ", "") + ".sh", pid],
                "items_opt": [],
                "attr": {
                    "title": args.title,
                    "porter": ["Samuka"],
                    "desc": "Port de " + args.title + " para PortMaster.",
                    "inst": "Instale o port e configure credenciais se necessário.",
                    "genres": [args.genre],
                    "image": None,
                    "rtr": False,
                    "exp": False,
                    "runtime": ["python_3.11"],
                    "store": [],
                    "availability": "full",
                    "reqs": [],
                    "arch": ["aarch64"],
                    "min_glibc": ""
                }
            }, f, indent=2, ensure_ascii=False)

    # gameinfo.xml
    gameinfo = os.path.join(pdir, "portmaster", "gameinfo.xml")
    if not os.path.exists(gameinfo):
        with open(gameinfo, "w", encoding="utf-8") as f:
            f.write('''<?xml version="1.0" encoding="utf-8"?>
<gameList>
  <game>
    <path>./{title}.sh</path>
    <name>{title}</name>
    <desc>Port de {title} para PortMaster.</desc>
    <developer>Samuka</developer>
    <publisher>Open Source</publisher>
    <genre>{genre}</genre>
  </game>
</gameList>
'''.format(title=args.title, genre=args.genre.capitalize()))

    # launcher .sh (simplificado, modelo CaVo)
    sh = os.path.join(pdir, args.title.replace(" ", "") + ".sh")
    if not os.path.exists(sh):
        with open(sh, "w", encoding="utf-8", newline="\n") as f:
            f.write('''#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GAMEDIR="$SCRIPT_DIR/{pid}"
cd "$GAMEDIR" || exit 1
export PYTHONPATH="$GAMEDIR:$GAMEDIR/core:${{PYTHONPATH:-}}"
python3 "$GAMEDIR/main.py"
'''.format(pid=pid))

    # requirements.txt (dependências Python do app)
    reqs = os.path.join(pdir, "requirements.txt")
    if not os.path.exists(reqs):
        with open(reqs, "w", encoding="utf-8") as f:
            f.write("# Dependencias Python do port (aarch64 / cp311).\\n")
            f.write("requests>=2.31\\n")
            f.write("# beautifulsoup4>=4.12   # scraping HTML\\n")
            f.write("# pillow>=10.0           # imagens\\n")

    # fetch_deps.py (modelo do port de ref)
    fetch = os.path.join(pdir, "fetch_deps.py")
    if not os.path.exists(fetch):
        with open(fetch, "w", encoding="utf-8") as f:
            f.write('''"""Baixa dependencias para o dispositivo (aarch64/cp311)."""
import subprocess, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
REQ = os.path.join(HERE, "requirements.txt")
OUT = os.path.join(HERE, "site-packages")
os.makedirs(OUT, exist_ok=True)
print("Instalando deps de", REQ, "em", OUT)
# Ajuste o index/plataforma conforme o dispositivo alvo.
subprocess.run([sys.executable, "-m", "pip", "install", "-r", REQ,
                "--target", OUT, "--upgrade"], check=False)
print("Pronto. Copie site-packages/ para o dispositivo.")
''')

    # README
    readme = os.path.join(pdir, "README.md")
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as f:
            f.write("# " + args.title + "\n\nPort gerado por tools/new_port.py.\n")

    print("Port criado em", pdir)


if __name__ == "__main__":
    main()