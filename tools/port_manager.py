#!/usr/bin/env python3
"""OddHub Port Manager: GUI para o registro da colecao.

Lista os apps de `ports/registry.json`, deixa mudar status, prioridade e nome,
criar port novo (usando `tools/new_port.py`), apagar e editar as notas de cada
port em `ports/<id>/NOTES.md`.
"""
from __future__ import annotations

import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path
from tkinter import (
    BOTH,
    LEFT,
    RIGHT,
    StringVar,
    Tk,
    Toplevel,
    X,
    Y,
    messagebox,
    scrolledtext,
    ttk,
)

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "ports" / "registry.json"
PORTS_DIR = ROOT / "ports"
NEW_PORT = ROOT / "tools" / "new_port.py"

STATUSES = ("planejado", "em andamento", "em teste", "funcional", "pausado")
GENRES = (
    "other",
    "action",
    "adventure",
    "arcade",
    "casino/card",
    "fps",
    "platformer",
    "puzzle",
    "racing",
    "rhythm",
    "rpg",
    "simulation",
    "sports",
    "strategy",
    "visual novel",
)


def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {"core": {}, "oddhub": {}, "apps": []}


def save_registry(data: dict) -> None:
    REGISTRY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def notes_path(app_id: str) -> Path:
    return PORTS_DIR / app_id / "NOTES.md"


def load_notes(app_id: str) -> list[str]:
    path = notes_path(app_id)
    if not path.exists():
        return []
    return [line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()]


def save_notes(app_id: str, lines: list[str]) -> None:
    path = notes_path(app_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(lines).strip()
    path.write_text(f"# Notas - {app_id}\n\n{body}\n", encoding="utf-8")


class PortManager:
    def __init__(self, root: Tk):
        self.root = root
        root.title("OddHub Port Manager")
        root.geometry("880x540")
        self.registry = load_registry()
        self.apps = self.registry.setdefault("apps", [])
        self.status_var = StringVar(value=STATUSES[0])
        self._build()
        self.refresh()

    # -- interface ----------------------------------------------------------
    def _build(self) -> None:
        top = ttk.Frame(self.root)
        top.pack(fill=X, padx=6, pady=6)
        ttk.Label(top, text="Status:").pack(side=LEFT)
        ttk.Combobox(
            top, textvariable=self.status_var, values=STATUSES, state="readonly", width=16
        ).pack(side=LEFT, padx=6)
        ttk.Button(top, text="Aplicar status", command=self.change_status).pack(side=LEFT)
        ttk.Button(top, text="Recalcular prioridade", command=self.renumber).pack(side=LEFT, padx=6)

        columns = ("id", "name", "type", "approach", "status", "priority")
        frame = ttk.Frame(self.root)
        frame.pack(fill=BOTH, expand=True, padx=6)
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        for column in columns:
            self.tree.heading(column, text=column.capitalize())
            self.tree.column(column, width=120, anchor="center")
        self.tree.column("name", width=180)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        bar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=bar.set)
        bar.pack(side=RIGHT, fill=Y)
        self.tree.bind("<Double-1>", lambda _event: self.edit_app())
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._sync_selection())

        buttons = ttk.Frame(self.root)
        buttons.pack(fill=X, padx=6, pady=6)
        for label, command in (
            ("Novo port", self.new_port),
            ("Editar", self.edit_app),
            ("Notas", self.edit_notes),
            ("Excluir", self.delete_apps),
            ("Subir", lambda: self.move(-1)),
            ("Descer", lambda: self.move(1)),
            ("Salvar", self.save),
        ):
            ttk.Button(buttons, text=label, command=command).pack(side=LEFT, padx=2)
        ttk.Button(buttons, text="Sair", command=self.root.destroy).pack(side=RIGHT)

        self.status = ttk.Label(self.root, text="", anchor="w")
        self.status.pack(fill=X, padx=6, pady=(0, 6))

    def _sync_selection(self) -> None:
        selected = self.tree.selection()
        self.selected = selected[0] if selected else None

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for app in self.apps:
            self.tree.insert(
                "",
                "end",
                iid=app["id"],
                values=(
                    app.get("id", ""),
                    app.get("name", ""),
                    app.get("type", ""),
                    app.get("approach", ""),
                    app.get("status", ""),
                    app.get("priority", ""),
                ),
            )

    def _selected_ids(self) -> list[str]:
        return list(self.tree.selection())

    def _set_status_message(self, text: str) -> None:
        self.status.configure(text=text)

    # -- acoes --------------------------------------------------------------
    def change_status(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showwarning("Aviso", "Selecione um ou mais apps.")
            return
        value = self.status_var.get()
        for app in self.apps:
            if app["id"] in ids:
                app["status"] = value
        self.save()
        self._set_status_message(f"{len(ids)} app(s) marcado(s) como {value}.")

    def renumber(self) -> None:
        """Prioridade 1 = primeiro da lista."""
        for index, app in enumerate(self.apps, start=1):
            app["priority"] = index
        self.save()
        self._set_status_message("Prioridades recalculadas.")

    def move(self, delta: int) -> None:
        ids = self._selected_ids()
        if len(ids) != 1:
            messagebox.showwarning("Aviso", "Selecione apenas um app para reordenar.")
            return
        app_id = ids[0]
        index = next((i for i, app in enumerate(self.apps) if app["id"] == app_id), -1)
        target = index + delta
        if index < 0 or not (0 <= target < len(self.apps)):
            return
        self.apps[index], self.apps[target] = self.apps[target], self.apps[index]
        self.renumber()
        self.refresh()
        self.tree.selection_set(app_id)

    def new_port(self) -> None:
        dialog = Toplevel(self.root)
        dialog.title("Novo port")
        dialog.geometry("440x300")
        form = ttk.Frame(dialog)
        form.pack(fill=BOTH, expand=True, padx=10, pady=10)

        fields: dict[str, ttk.Entry] = {}
        rows = (("Id (pasta e registro)", "id"), ("Titulo (aparece no PortMaster)", "title"),
                ("Pacote python (opcional)", "package"), ("Descricao", "desc"))
        for index, (label, key) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=index, column=0, sticky="w", pady=3)
            entry = ttk.Entry(form, width=36)
            entry.grid(row=index, column=1, pady=3)
            fields[key] = entry

        ttk.Label(form, text="Genero").grid(row=len(rows), column=0, sticky="w", pady=3)
        genre_var = StringVar(value="other")
        ttk.Combobox(
            form, textvariable=genre_var, values=GENRES, state="readonly", width=33
        ).grid(row=len(rows), column=1, pady=3)

        def create() -> None:
            app_id = fields["id"].get().strip().lower()
            title = fields["title"].get().strip()
            if not app_id or not title:
                messagebox.showerror("Erro", "Informe o id e o titulo.", parent=dialog)
                return
            if (PORTS_DIR / app_id).exists():
                messagebox.showerror("Erro", f"A pasta ports/{app_id} ja existe.", parent=dialog)
                return
            command = [sys.executable, str(NEW_PORT), app_id, title, "--genre", genre_var.get()]
            if fields["package"].get().strip():
                command += ["--package", fields["package"].get().strip()]
            if fields["desc"].get().strip():
                command += ["--desc", fields["desc"].get().strip()]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                messagebox.showerror("Erro", result.stdout + result.stderr, parent=dialog)
                return
            self.registry = load_registry()
            self.apps = self.registry.setdefault("apps", [])
            self.save()
            self.refresh()
            dialog.destroy()
            self._set_status_message(f"Port {app_id} criado. Rode sync_core.py {app_id}.")

        ttk.Button(form, text="Criar", command=create).grid(row=len(rows) + 1, column=1, sticky="e", pady=8)

    def edit_app(self) -> None:
        ids = self._selected_ids()
        if len(ids) != 1:
            messagebox.showwarning("Aviso", "Selecione um app.")
            return
        app = next((item for item in self.apps if item["id"] == ids[0]), None)
        if not app:
            return
        dialog = Toplevel(self.root)
        dialog.title(f"Editar {app['id']}")
        dialog.geometry("440x300")
        form = ttk.Frame(dialog)
        form.pack(fill=BOTH, expand=True, padx=10, pady=10)

        name_var = StringVar(value=app.get("name", ""))
        type_var = StringVar(value=app.get("type", ""))
        approach_var = StringVar(value=app.get("approach", ""))
        status_var = StringVar(value=app.get("status", STATUSES[0]))
        priority_var = StringVar(value=str(app.get("priority", 0)))

        for index, (label, var, values) in enumerate((
            ("Nome", name_var, None),
            ("Tipo", type_var, None),
            ("Abordagem", approach_var, None),
            ("Status", status_var, STATUSES),
            ("Prioridade", priority_var, None),
        )):
            ttk.Label(form, text=label).grid(row=index, column=0, sticky="w", pady=3)
            if values:
                ttk.Combobox(form, textvariable=var, values=values, state="readonly", width=33).grid(
                    row=index, column=1, pady=3
                )
            else:
                ttk.Entry(form, textvariable=var, width=35).grid(row=index, column=1, pady=3)

        def apply() -> None:
            app["name"] = name_var.get().strip() or app["id"]
            app["type"] = type_var.get().strip()
            app["approach"] = approach_var.get().strip()
            app["status"] = status_var.get()
            try:
                app["priority"] = int(priority_var.get())
            except ValueError:
                messagebox.showerror("Erro", "Prioridade precisa ser um numero.", parent=dialog)
                return
            self.save()
            self.refresh()
            dialog.destroy()

        ttk.Button(form, text="Salvar", command=apply).grid(
            row=6, column=1, sticky="e", pady=8
        )

    def edit_notes(self) -> None:
        ids = self._selected_ids()
        if len(ids) != 1:
            messagebox.showwarning("Aviso", "Selecione um app.")
            return
        app_id = ids[0]
        dialog = Toplevel(self.root)
        dialog.title(f"Notas de {app_id}")
        dialog.geometry("620x440")
        text = scrolledtext.ScrolledText(dialog, wrap="word")
        text.pack(fill=BOTH, expand=True, padx=6, pady=6)
        existing = [line for line in load_notes(app_id) if line.strip() and not line.startswith("#")]
        text.insert("1.0", "\n".join(existing))

        def save() -> None:
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            lines = []
            for line in text.get("1.0", "end-1c").splitlines():
                line = line.strip()
                if not line:
                    continue
                lines.append(line if line.startswith("- [") else f"- [{stamp}] {line}")
            save_notes(app_id, lines)
            dialog.destroy()
            self._set_status_message(f"Notas de {app_id} salvas.")

        ttk.Button(dialog, text="Salvar", command=save).pack(pady=6)

    def delete_apps(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showwarning("Aviso", "Selecione um ou mais apps.")
            return
        if not messagebox.askyesno(
            "Confirmar", f"Excluir {len(ids)} app(s)?\n\n{', '.join(ids)}\n\nAs pastas serao apagadas."
        ):
            return
        for app_id in ids:
            folder = PORTS_DIR / app_id
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
        self.apps = [app for app in self.apps if app["id"] not in ids]
        self.save()
        self.refresh()
        self._set_status_message(f"{len(ids)} app(s) excluido(s).")

    def save(self) -> None:
        self.registry["apps"] = self.apps
        save_registry(self.registry)
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "tracker.py"), "--write"],
            capture_output=True,
        )


def main() -> None:
    root = Tk()
    PortManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()