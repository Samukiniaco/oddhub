"""Ajudantes de texto usados na interface (sem dependencia do pygame)."""
from __future__ import annotations


def initials(name: str) -> str:
    """Iniciais para o avatar: 'Ana Costa' vira 'AC', 'ana' vira 'AN'."""
    parts = [p for p in (name or "").replace("_", " ").replace("-", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def preview(text: str, limit: int = 90) -> str:
    """Texto de uma linha, cortado."""
    text = " ".join((text or "").split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "..."
    return text
