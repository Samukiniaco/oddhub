"""Tema visual: paleta e medidas compartilhadas.

Cada port instancia um `Theme` e sobrescreve o que quiser. Os valores aqui
sao o padrao da colecao, pensados para tela escura e leitura em 640x480.
"""
from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass
class Theme:
    """Paleta e medidas de um port."""

    # fundo e superficies
    bg: tuple = (18, 20, 24)
    header: tuple = (24, 27, 33)
    header_2: tuple = (32, 36, 43)
    panel: tuple = (28, 31, 37)
    panel_2: tuple = (43, 47, 56)
    panel_3: tuple = (55, 60, 70)
    divider: tuple = (44, 48, 57)

    # texto
    text: tuple = (233, 236, 240)
    text_dim: tuple = (150, 157, 166)
    text_faint: tuple = (104, 110, 120)

    # acoes
    accent: tuple = (122, 148, 224)
    accent_dark: tuple = (92, 116, 190)
    select: tuple = (36, 40, 48)
    select_strong: tuple = (122, 148, 224)
    unread: tuple = (122, 148, 224)
    danger: tuple = (211, 73, 68)
    warning: tuple = (224, 168, 62)
    ok: tuple = (76, 175, 120)
    white: tuple = (255, 255, 255)
    black: tuple = (0, 0, 0)

    def copy(self, **changes) -> "Theme":
        """Devolve uma copia do tema com os campos trocados."""
        data = {f.name: getattr(self, f.name) for f in fields(self)}
        data.update(changes)
        return Theme(**data)
