"""Acompanhamento simples dos ports. Modo texto por padrao; --gui abre tkinter."""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "ports", "registry.json")


def load():
    with open(REG, encoding="utf-8") as f:
        return json.load(f)


def show_text():
    d = load()
    print("== core:", d["core"]["status"], "-", d["core"]["notes"])
    print("== oddhub:", d["oddhub"]["status"], "-", d["oddhub"]["notes"])
    print("\nApps:")
    for a in d["apps"]:
        print(f"  {a['id']:14} {a['status']:14} {a['approach']}")


def show_gui():
    import tkinter as tk
    from tkinter import ttk
    d = load()
    root = tk.Tk()
    root.title("OddHub Tracker")
    cols = ("id", "name", "type", "approach", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c)
    for a in d["apps"]:
        tree.insert("", "end", values=tuple(a.get(c, "") for c in cols))
    tree.pack(fill="both", expand=True)
    root.mainloop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gui", action="store_true")
    args = ap.parse_args()
    if args.gui:
        show_gui()
    else:
        show_text()


if __name__ == "__main__":
    main()