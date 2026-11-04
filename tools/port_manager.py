#!/usr/bin/env python3
"""OddHub Port Manager — GUI para listar/editar status e notas de cada app.

Usa como base os dados de `ports/registry.json` e `NOTES.md`.
Permite marcar status, adicionar/editar notas, gerenciar apps (novo/excluir) e definir prioridades.
"""
import json
import os
import sys
import shutil
from pathlib import Path
from tkinter import Tk, ttk, messagebox, scrolledtext, Toplevel, StringVar, OptionMenu, Label, Button, Entry, Frame
import subprocess

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

        # Treeview para listar apps (inclui priority)
        tree_frame = ttk.Frame(self.root)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        columns = ("id", "name", "type", "approach", "status", "priority")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=120, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # Botões inferiores
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text="Adicionar Nota", command=self.add_note).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Novo App", command=self.add_app).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Excluir App", command=self.delete_app).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Subir", command=self.move_up).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Descer", command=self.move_down).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Salvar", command=self.save_changes).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Sair", command=self.root.destroy).pack(side="right", padx=2)

        self.selected_app_id = None

    def on_select(self, _event=None):
        sel = self.tree.selection()
        self.selected_app_id = sel[0] if sel else None

    def _index_selected(self):
        for i, a in enumerate(self.apps):
            if a["id"] == self.selected_app_id:
                return i
        return -1

    def move_up(self):
        i = self._index_selected()
        if i > 0:
            self.apps[i - 1], self.apps[i] = self.apps[i], self.apps[i - 1]
            self._persist()
            self.refresh_tree()
            self.tree.selection_set(self.selected_app_id)

    def move_down(self):
        i = self._index_selected()
        if 0 <= i < len(self.apps) - 1:
            self.apps[i + 1], self.apps[i] = self.apps[i], self.apps[i + 1]
            self._persist()
            self.refresh_tree()
            self.tree.selection_set(self.selected_app_id)

    def refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for app in self.apps:
            self.tree.insert("", "end", iid=app["id"], values=(
                app["id"],
                app["name"],
                app["type"],
                app["approach"],
                app.get("status", "planejado"),
                app.get("priority", 0)
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

    def _persist(self):
        self.registry["apps"] = self.apps
        save_registry(self.registry)

    def save_changes(self):
        self._persist()
        messagebox.showinfo("Concluído", "Todas as alterações salvas.")

    def add_app(self):
        # Diálogo para adicionar um novo app
        dlg = Toplevel(self.root)
        dlg.title("Novo App")
        dlg.geometry("300x250")
        form = Frame(dlg)
        form.pack(padx=10, pady=10)
        fields = {}
        labels = [("ID", "id"), ("Nome", "name"), ("Tipo", "type"), ("Aproximação", "approach"), ("Status", "status"), ("Prioridade", "priority")]
        for lbl, key in labels:
            Label(form, text=lbl).grid(row=len(fields), column=0, sticky="w")
            if key == "status":
                var = StringVar(value="planejado")
                opts = OptionMenu(form, var, "planejado", "em andamento", "protótipo", "funcional", "pausado")
                opts.grid(row=len(fields), column=1)
                fields[key] = var
            else:
                ent = Entry(form)
                ent.grid(row=len(fields), column=1)
                fields[key] = ent
        def submit():
            # validar id unico
            new_id = fields["id"].get().strip().lower()
            if not new_id or not new_id.isalnum():
                messagebox.showerror("Erro", "ID deve ser alfanumérico e não vazio")
                return
            if any(a["id"] == new_id for a in self.apps):
                messagebox.showerror("Erro", f"App com ID '{new_id}' já existe")
                return
            name = fields["name"].get().strip() or new_id
            app_type = fields["type"].get().strip() or "utility"
            approach = fields["approach"].get().strip() or "planejado"
            status = fields["status"].get() or "planejado"
            try:
                priority = int(fields["priority"].get() or 0)
            except ValueError:
                priority = 0
            # gerar port usando tools/new_port.py (caminho absoluto)
            script = str(ROOT / "tools" / "new_port.py")
            try:
                subprocess.run([sys.executable, script, new_id, name, "--genre", app_type], check=True)
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Erro", f"Falha ao gerar port: {e}")
                return
            # registra no registry.json
            self.apps.append({
                "id": new_id,
                "name": name,
                "type": app_type,
                "approach": approach,
                "status": status,
                "priority": priority,
            })
            self.save_changes()
            self.refresh_tree()
            dlg.destroy()
            messagebox.showinfo("Sucesso", f"App '{new_id}' criado com sucesso.")
        btn = Button(dlg, text="Criar", command=submit)
        btn.grid(row=len(fields)+1, column=0, columnspan=2, pady=5)

    def delete_app(self):
        if not self.selected_app_id:
            messagebox.showwarning("Aviso", "Selecione um app para excluir.")
            return
        app_id = self.selected_app_id
        if not messagebox.askyesno("Confirmar", f"Excluir o app '{app_id}'? Isso removerá o diretório do port."):
            return
        # remover do registry
        self.apps = [a for a in self.apps if a["id"] != app_id]
        # deletar diretório do port
        port_dir = ROOT / "ports" / app_id
        if port_dir.exists():
            shutil.rmtree(port_dir, ignore_errors=True)
        self.selected_app_id = None
        self.save_changes()
        self.refresh_tree()
        messagebox.showinfo("Excluído", f"App '{app_id}' excluído.")

    def edit_priority(self):
        if not self.selected_app_id:
            messagebox.showwarning("Aviso", "Selecione um app para editar prioridade.")
            return
        # abrir diálogo para editar prioridade
        dlg = Toplevel(self.root)
        dlg.title("Editar Prioridade")
        Label(dlg, text="Prioridade (número):").pack(padx=10, pady=5)
        entry = Entry(dlg)
        entry.insert(0, str(next((a.get("priority", 0) for a in self.apps if a["id"] == self.selected_app_id), 0)))
        entry.pack(padx=10, pady=5)
        def submit():
            try:
                prio = int(entry.get())
                for a in self.apps:
                    if a["id"] == self.selected_app_id:
                        a["priority"] = prio
                        break
                self.save_changes()
                self.refresh_tree()
                dlg.destroy()
                messagebox.showinfo("Sucesso", "Prioridade atualizada.")
            except ValueError:
                messagebox.showerror("Erro", "Prioridade deve ser um número.")
        Button(dlg, text="OK", command=submit).pack(pady=5)


def main():
    root = Tk()
    app = PortManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()