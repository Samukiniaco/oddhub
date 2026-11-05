"""Backend offline (demo) — pins e boards de exemplo sem internet."""
from __future__ import annotations

import time
import zlib
from pathlib import Path
from typing import Optional

from ..models import Board, Pin
from .base import Backend

# (board_id, board_title, pin_title, descrição, tags, aspect, minutos atrás, saves)
_SEED_BOARDS = [
    ("demo:recipes", "Receitas", "Pratos rápidos e fáceis para o dia a dia", ""),
    ("demo:art", "Arte & Ilustração", "Referências artísticas e ilustrações", ""),
    ("demo:diy", "DIY & Crafts", "Projetos manuais para fazer em casa", ""),
    ("demo:fashion", "Moda", "Inspirações de look e estilo", ""),
    ("demo:tech", "Tech & Setup", "Setups, gadgets e produtividade", ""),
]

_SEED_PINS = [
    # (board, título, descrição, tags, aspect, minutos, saves)
    ("demo:recipes", "Pão de queijo de airfryer",
     "Receita rápida com poucos ingredientes. Fica pronto em 15 minutos!",
     ["comida", "airfryer", "café da manhã"], 0.75, 30, 1240),
    ("demo:recipes", "Bolo de chocolate de caneca",
     "Sobremesa em 2 minutos no micro-ondas. Perfeito para o café.",
     ["comida", "sobremesa", "rápido"], 1.0, 95, 890),
    ("demo:recipes", "Salada de grão-de-bico",
     "Almoço saudável e prático com proteína vegetal.",
     ["comida", "saudável", "almoço"], 0.8, 180, 456),
    ("demo:recipes", "Café coado perfeito",
     "Dicas de moagem, temperatura e tempo para extrair o melhor sabor.",
     ["café", "dicas"], 0.7, 300, 2310),
    ("demo:recipes", "Torta de limão gelada",
     "Sobremesa cítrica e refrescante para dias quentes.",
     ["sobremesa", "limão"], 0.75, 1440, 670),

    ("demo:art", "Estudo de luz em aquarela",
     "Como trabalhar luz e sombra com aquarela em 3 passos.",
     ["aquarela", "tutorial", "luz"], 0.7, 45, 3400),
    ("demo:art", "Paleta de cores outono",
     "Combinações de cores quentes para ilustração e design.",
     ["cores", "paleta", "design"], 1.0, 120, 1890),
    ("demo:art", "Anatomia de mãos — referência",
     "Seleção de poses de mãos para estudo de anatomia.",
     ["anatomia", "referência", "desenho"], 0.8, 240, 5100),
    ("demo:art", "Ilustração cyberpunk",
     "Cena urbana futurista com neon e chuva.",
     ["ilustração", "cyberpunk", "arte digital"], 0.75, 480, 2210),
    ("demo:art", "Lettering a mão livre",
     "Alfabeto decorativo com pincel e tinta preta.",
     ["lettering", "tipografia"], 1.2, 720, 980),

    ("demo:diy", "Organizador de mesa com EVA",
     "Passo a passo simples para organizar sua mesa de estudos.",
     ["diy", "organização", "eva"], 0.8, 60, 760),
    ("demo:diy", "Vaso suspenso de macramê",
     "Tutorial iniciante de macramê para decoração.",
     ["macramê", "decoração"], 0.7, 200, 1450),
    ("demo:diy", "Luminária de papel",
     "Abajur artesonal com papel reciclado e LED.",
     ["luminária", "papel", "reciclagem"], 1.0, 400, 540),
    ("demo:diy", "Mesa de cabeceira minimalista",
     "Projeto de marcenaria simples para iniciantes.",
     ["marcenaria", "móvel"], 0.75, 1000, 3020),

    ("demo:fashion", "Look casual com jaqueta jeans",
     "Combinação fácil para o dia a dia com peças básicas.",
     ["moda", "jeans", "look"], 0.7, 25, 4100),
    ("demo:fashion", "Tênis branco: 5 formas de usar",
     "Ideias de looks com o tênis branco neutro.",
     ["moda", "tênis"], 0.8, 150, 2670),
    ("demo:fashion", "Acessórios dourados",
     "Como combinar joias douradas sem exagerar.",
     ["joias", "acessórios"], 1.0, 600, 1330),
    ("demo:fashion", "Outono em tons terrosos",
     "Paleta de roupas para o outono com tons terrosos.",
     ["moda", "outono", "cores"], 0.7, 1500, 890),

    ("demo:tech", "Setup minimalista 2026",
     "Mesa limpa com monitor ultrawide e iluminação atrás.",
     ["setup", "minimalista"], 1.3, 15, 8900),
    ("demo:tech", "Teclado mecânico silencioso",
     "Opcões de switches silenciosos para trabalhar à noite.",
     ["teclado", "mecânico"], 0.8, 90, 3200),
    ("demo:tech", "Atalhos que aumentam produtividade",
     "Lista de atalhos de teclado para programadores.",
     ["produtividade", "atalhos", "código"], 1.0, 360, 6100),
    ("demo:tech", "Cadeira ergonômica barata",
     "Opções de cadeira com bom custo-benefício.",
     ["ergonomia", "cadeira"], 0.75, 900, 1740),

    ("demo:recipes", "Smoothie verde matinal",
     "Espinafre, banana e maçã para começar o dia bem.",
     ["saudável", "bebida"], 0.7, 2100, 520),
    ("demo:art", "Grid de perspectiva",
     "Como usar pontos de fuga na composição de cenários.",
     ["perspectiva", "desenho", "tutorial"], 1.1, 2600, 4300),
    ("demo:diy", "Estante flutuante",
     "Estante aparente sem suporte visível, passo a passo.",
     ["estante", "parede", "diy"], 1.25, 3300, 1980),
    ("demo:tech", "Cabo organizado de verdade",
     "Grips e canal para acabar com a bagunça de cabos.",
     ["setup", "organização"], 0.75, 4400, 2870),
]


class DemoBackend(Backend):
    id = "demo"
    label = "Demo offline"
    real = False

    def __init__(self, store, data_dir: Optional[Path] = None):
        super().__init__(store, data_dir)

    def start(self) -> None:
        super().start()
        if not self.store.get_boards():
            self._seed()
        self.set_status("demo", "dados locais")

    def _seed(self) -> None:
        now = time.time()
        for board_id, title, description, _ in _SEED_BOARDS:
            self.store.upsert_board(Board(id=board_id, title=title, description=description))
        counts: dict[str, int] = {}
        for board_id, title, description, tags, aspect, minutes_ago, saves in _SEED_PINS:
            # id determinístico (hash() do Python é aleatório por processo)
            digest = zlib.crc32(title.encode("utf-8"))
            pin = Pin(
                id=f"demo:{digest:08x}",
                board_id=board_id,
                title=title,
                description=description,
                url=f"https://www.pinterest.com/pin/{digest:08x}/",
                author="Pinterest Demo",
                tags=tags,
                aspect=aspect,
                saves=saves,
                ts=now - minutes_ago * 60,
                seed=digest % 1000,
            )
            self.store.upsert_pin(pin)
            counts[board_id] = counts.get(board_id, 0) + 1
        for board in self.store.get_boards():
            board.pin_count = counts.get(board.id, 0)
            self.store.upsert_board(board)
        self.emit("pins")

    def refresh(self) -> None:
        self.emit("pins")
        self.set_status("demo", "dados locais")
