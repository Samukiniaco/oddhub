"""CaVo — resolve qual sprite cada jogador usa (sprites_tool.py organiza).

Ordem: manifest (sprites/manifest.json, slots p1/p2) -> legado sprites/p1.png -> None.
"""
import json
import os

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(_BASE, "sprites", "manifest.json")

_cache = None


def manifest():
    global _cache
    if _cache is None:
        try:
            with open(MANIFEST, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, ValueError):
            _cache = {}
    return _cache


def reload():
    global _cache
    _cache = None


def path_for_slot(slot):
    """Caminho relativo (p/ player.load_sprite) ou None."""
    m = manifest()
    name = m.get(slot)
    if name:
        return f"sprites/{name}"
    legacy = f"sprites/{slot}.png"
    if os.path.isfile(os.path.join(_BASE, legacy)):
        return legacy
    return None
