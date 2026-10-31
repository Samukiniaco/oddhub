#!/usr/bin/env python3
"""Adiciona uma nota rápida a NOTES.md.
Uso: python tools/note.py "WhatsApp - ver API web"
"""
import sys, datetime, os

NOTE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "NOTES.md")

def main():
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Nota: ")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(NOTE, "a", encoding="utf-8") as f:
        f.write(f"- [{ts}] {text}\n")
    print("Nota adicionada.")

if __name__ == "__main__":
    main()
