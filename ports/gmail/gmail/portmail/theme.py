"""Tema do PortMail.

O core traz a paleta padrao da colecao; cada port define a sua. O PortMail
usa um azul de correio, sem copiar a identidade visual de nenhum servico de
email (nada de logo, cor de marca ou layout imitado).
"""
from __future__ import annotations

from core.theme import Theme

THEME = Theme(
    bg=(18, 20, 24),
    header=(24, 27, 33),
    header_2=(32, 36, 43),
    panel=(28, 31, 37),
    panel_2=(43, 47, 56),
    panel_3=(55, 60, 70),
    divider=(44, 48, 57),
    text=(233, 236, 240),
    text_dim=(150, 157, 166),
    text_faint=(104, 110, 120),
    accent=(104, 168, 214),
    accent_dark=(76, 128, 168),
    select=(36, 40, 48),
    select_strong=(104, 168, 214),
    unread=(104, 168, 214),
    danger=(211, 73, 68),
    warning=(224, 168, 62),
    ok=(76, 175, 120),
)
