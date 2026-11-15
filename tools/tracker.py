"""Acompanhamento dos ports da colecao.

    python tools/tracker.py            # lista no terminal
    python tools/tracker.py --gui      # janela tkinter
    python tools/tracker.py --write    # gera o PORTS.md a partir do registro
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "ports" / "registry.json"
PORTS_MD = ROOT / "PORTS.md"

STATUS_LEGEND = (
    "planejado (esta no registro, sem codigo) | "
    "em andamento (codigo comecando) | "
    "em teste (rodando, falta testar no aparelho) | "
    "funcional (rodando e testado) | "
    "pausado"
)


def load() -> dict:
    if not REGISTRY.exists():
        return {"core": {}, "oddhub": {}, "apps": []}
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"core": {}, "oddhub": {}, "apps": []}


def show_text() -> None:
    data = load()
    core = data.get("core") or {}
    hub = data.get("oddhub") or {}
    if core:
        print(f"== core: {core.get('status', '-')} - {core.get('notes', '')}")
    if hub:
        print(f"== oddhub: {hub.get('status', '-')} - {hub.get('notes', '')}")
    print("\nApps:")
    for app in data.get("apps", []):
        print(
            f"  {app.get('id', ''):14} {app.get('status', ''):14} "
            f"{app.get('approach', ''):16} {app.get('name', '')}"
        )


def show_gui() -> None:
    import tkinter as tk
    from tkinter import ttk

    data = load()
    root = tk.Tk()
    root.title("OddHub Tracker")
    cols = ("id", "name", "type", "approach", "status", "priority")
    tree = ttk.Treeview(root, columns=cols, show="headings")
    for column in cols:
        tree.heading(column, text=column)
    for app in data.get("apps", []):
        tree.insert("", "end", values=tuple(app.get(column, "") for column in cols))
    tree.pack(fill="both", expand=True)
    root.mainloop()


def write_markdown() -> None:
    """Gera o PORTS.md a partir do registro."""
    data = load()
    lines = [
        "# PORTS.md - acompanhamento da colecao",
        "",
        "Este arquivo e gerado por `python tools/tracker.py --write`.",
        "O registro que manda e `ports/registry.json`.",
        "",
        f"Legenda de status: {STATUS_LEGEND}",
        "",
        "## Nucleo e gerenciador",
        "",
        "| Item | Status | Notas |",
        "|------|--------|-------|",
    ]
    for key, label in (("core", "core (base compartilhada)"), ("oddhub", "oddhub (gerenciador)")):
        entry = data.get(key) or {}
        if entry:
            lines.append(f"| {label} | {entry.get('status', '-')} | {entry.get('notes', '')} |")
    lines += [
        "",
        "## Apps",
        "",
        "| Id | Port | Tipo | Abordagem | Status | Prioridade |",
        "|----|------|------|-----------|--------|------------|",
    ]
    for app in data.get("apps", []):
        lines.append(
            f"| {app.get('id', '')} | {app.get('name', '')} | {app.get('type', '')} | "
            f"{app.get('approach', '')} | {app.get('status', '')} | {app.get('priority', '')} |"
        )
    lines += [
        "",
        "## Como mexer",
        "",
        "- `python tools/new_port.py <id> \"Nome\"` cria um port novo a partir do template",
        "- `python tools/sync_core.py <id>` copia o core para dentro do port",
        "- `python tools/build_all.py` monta os zips de teste",
        "- `python tools/port_manager.py` abre o gerenciador grafico do registro",
        "",
    ]
    PORTS_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"{PORTS_MD} atualizado")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true", help="abre a janela tkinter")
    parser.add_argument("--write", action="store_true", help="gera o PORTS.md")
    args = parser.parse_args()
    if args.write:
        write_markdown()
    elif args.gui:
        show_gui()
    else:
        show_text()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
