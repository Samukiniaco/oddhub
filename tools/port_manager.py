#!/usr/bin/env python3
"""OddHub Port Manager — GUI para listar/editar status e notas de cada app.

Usa como base os dados de `ports/registry.json` e `NOTES.md`.
Permite marcar status, adicionar/editar notas, e salvar tudo.
"""
import json
import os
import sys
from pathlib import Path
from tkinter import Tk, ttk, messagebox, scrolledtext, Toplevel, StringVar, OptionMenu, Label, Button

ROOT = Path(__file__).parent.parent
REGISTRY_PATH = ROOT / "ports" / "registry.json"
NOTES_PATH = ROOT / "NOTES.md"

# Carrega os dados globais uma vez
REGISTRY_DATA = None

def load_registry():
    global REGISTRY_DATA
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            REGISTRY_DATA = json.load(f)
    else:
        REGISTRY_DATA = {"core": {}, "oddhub": {}, "apps": []}
    return REGISTRY_DATA

def save_registry(data=None):
    global REGISTRY_DATA
    if data is not None:
        REGISTRY_DATA = data
    if REGISTRY_DATA is None:
        return
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(REGISTRY_DATA, f, ensure_ascii=False, indent=2)

def load_notes():
    """Retorna dict app_id -> list de notas (linhas) de NOTES.md."""
    notes = {}
    if not NOTES_PATH.exists():
        return notes
    with open(NOTES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith("-"):
                continue
            # formato: - [2026-10-30 22:18] App - texto
            if " - " in line:
                parts = line[2:].split(" - ", 1)
                hint = parts[1] if len(parts) > 1 else ""
                # associa a apps cujo id aparece no hint
                for app in REGISTRY_DATA.get("apps", []):
                    if app["id"] in hint or app["name"] in hint:
                        notes.setdefault(app["id"], []).append(line)
                        break
    return notes


def save_notes(notes_by_id):
    """Escreve o arquivo de notas inteiro."""
    lines = [
        "# Notas de pesquisa — OddHub",
        "",
        "Use `python tools/note.py \"texto\"` para adicionar rapidamente.",
        "Ou edite este arquivo diretamente.",
        "",
        "---"
    ]
    for note_lines in notes_by_id.values():
        for ln in note_lines:
            lines.append(ln)
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


class PortManagerApp:
    def __init__(self, root):
        self.root = root
        root.title("OddHub Port Manager")
        root.geometry("800x500")
        self.registry = load_registry()
        self.apps = self.registry.get("apps", [])
        self.notes = load_notes()
        self.setup_ui()
        self.refresh_tree()

    def setup_ui(self):
        # Frame superior para selecionar app e status
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=5, pady=5)
        ttk.Label(top, text="App:", font=("Helvetica", 10, "bold")).pack(side="left")
        self.status_var = StringVar(value="planejado")
        status_combo = OptionMenu(top, self.status_var, "planejado", "em andamento", "protótipo", "funcional", "pausado")
        status_combo.pack(side="left", padx=5)
        ttk.Button(top, text="Alterar Status", command=self.change_status).pack(side="left", padx=5)

        # Treeview para listar apps
        tree_frame = ttk.Frame(self.root)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        columns = ("id", "name", "type", "approach", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=120, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.on_double_click)

        # Botões inferiores
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text="Adicionar Nota", command=self.add_note).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Salvar", command=self.save_changes).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Sair", command=self.root.destroy).pack(side="right", padx=2)

        self.selected_app_id = None

    def refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for app in self.apps:
            self.tree.insert("", "end", iid=app["id"], values=(
                app["id"],
                app["name"],
                app["type"],
                app["approach"],
                app.get("status", "planejado")
            ))

    def on_double_click(self, event):
        item_id = self.tree.selection()[0] if self.tree.selection() else None
        if item_id:
            self.selected_app_id = item_id
            self.edit_note()

    def change_status(self):
        if not self.selected_app_id:
            messagebox.showwarning("Aviso", "Selecione um app primeiro.")
            return
        new_status = self.status_var.get()
        for app in self.apps:
            if app["id"] == self.selected_app_id:
                app["status"] = new_status
                self.refresh_tree()
                break
        messagebox.showinfo("Status alterado", f"App {self.selected_app_id} marcado como {new_status}")

    def add_note(self):
        if not self.selected_app_id:
            messagebox.showwarning("Aviso", "Selecione um app primeiro.")
            return
        note_window = Toplevel(self.root)
        note_window.title(f"Nota para {self.selected_app_id}")
        note_window.geometry("400x300")
        note_text = scrolledtext.ScrolledText(note_window, wrap="word")
        note_text.pack(fill="both", expand=True, padx=5, pady=5)
        # carrega notas existentes para o app
        existing = "\n".join(self.notes.get(self.selected_app_id, []))
        if existing:
            note_text.insert("1.0", existing)
        def save_note():
            lines = note_text.get("1.0", "end-1c").strip().split("\n")
            import datetime
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            # sobrescreve todas as linhas com as existentes mais as novas
            new_entries = []
            for ln in lines:
                if ln.strip():
                    new_entries.append(f"- [{ts}] {ln.strip()}")
            self.notes[self.selected_app_id] = new_entries
            save_notes(self.notes)
            note_window.destroy()
            messagebox.showinfo("Salvo", "Nota(s) salvas.")
        ttk.Button(note_window, text="Salvar", command=save_note).pack(pady=5)

    def save_changes(self):
        self.registry["apps"] = self.apps
        save_registry(self.registry)
        messagebox.showinfo("Concluído", "Todas as alterações salvas.")


def main():
    root = Tk()
    app = PortManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()