"""Tema do gerenciador OddHub (claro).

Visual de loja de apps: fundo claro, cards brancos, acentos coloridos por
categoria. Nada de copiar a identidade de outra loja: so o jeito claro e
cartao, que e uma linguagem visual comum.
"""

from __future__ import annotations

from core.theme import Theme

THEME = Theme(
    bg=(246, 247, 249),
    header=(255, 255, 255),
    header_2=(238, 240, 243),
    panel=(255, 255, 255),
    panel_2=(238, 240, 243),
    panel_3=(228, 231, 236),
    divider=(228, 231, 236),
    text=(32, 35, 40),
    text_dim=(112, 119, 130),
    text_faint=(156, 162, 172),
    accent=(58, 110, 214),
    accent_dark=(44, 88, 178),
    select=(232, 238, 250),
    select_strong=(58, 110, 214),
    unread=(58, 110, 214),
    danger=(206, 54, 54),
    warning=(198, 130, 20),
    ok=(38, 140, 96),
    white=(255, 255, 255),
    black=(20, 22, 26),
)

# Acentos por categoria (usados no "icone" de cada card)
CATEGORY_COLORS = {
    "mail": (66, 133, 244),
    "image": (214, 51, 108),
    "video": (214, 48, 49),
    "streaming": (240, 138, 20),
    "social": (36, 150, 130),
    "utility": (110, 120, 200),
    "game": (120, 90, 200),
}

CATEGORY_INITIALS = {
    "mail": "M",
    "image": "P",
    "video": "Y",
    "streaming": "C",
    "social": "S",
    "utility": "O",
    "game": "G",
}