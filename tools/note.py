#!/usr/bin/env python3
"""Adiciona uma nota rápida ao NOTES.md de um app.
Uso: python tools/note.py <app_id> "texto"
"""
import sys, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent

def main():
    if len(sys.argv) < 3:
        print("Uso: python tools/note.py <app_id> \"texto\"")
        sys.exit(1)
    app_id = sys.argv[1]
    text = " ".join(sys.argv[2:])
    note_path = ROOT / "ports" / app_id / "NOTES.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- [{ts}] {text}\n"
    with open(note_path, "a", encoding="utf-8") as f:
        f.write(line)
    print(f"Nota adicionada em {note_path}")

if __name__ == "__main__":
    main()