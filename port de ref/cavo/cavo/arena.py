"""CaVo — treino: balõezinhos espalhados pelo mundo (renascem perto de você)."""
import math
import random

import pygame

from . import config as C
from .graphics import draw


class Balloon:
    def __init__(self, near=None):
        self.reset(near=near)

    def reset(self, first=False, near=None):
        if near is not None:
            for _ in range(20):  # tenta nascer numa faixa de distância do jogador
                a = random.uniform(0, math.pi * 2)
                d = random.uniform(C.BALLOON_NEAR_MIN, C.BALLOON_NEAR_MAX)
                x = max(80, min(C.WORLD_W - 80, near.x + math.cos(a) * d))
                y = max(80, min(C.WORLD_H - 80, near.y + math.sin(a) * d))
                if abs(x - near.x) + abs(y - near.y) > C.BALLOON_NEAR_MIN:
                    break
            self.p = pygame.Vector2(x, y)
        else:
            self.p = pygame.Vector2(random.uniform(200, C.WORLD_W - 200),
                                    random.uniform(150, C.WORLD_H - 400) if first
                                    else random.uniform(150, 600))
        self.v = pygame.Vector2(random.uniform(-40, 40), random.uniform(20, 60))
        self.r = random.randint(14, 20)
        self.color = random.choice([(255, 110, 110), (140, 255, 160),
                                    (150, 180, 255), (255, 220, 120)])
        self.t = random.uniform(0, 6)

    def update(self, dt, near=None):
        self.t += dt
        self.p += self.v * dt
        self.p.x += math.sin(self.t * 2) * 30 * dt
        if near is not None and (self.p - near).length() > C.BALLOON_FAR:
            self.reset(near=near)
        else:
            self.p.x = max(40, min(C.WORLD_W - 40, self.p.x))
            self.p.y = max(40, min(C.WORLD_H - 40, self.p.y))

    def draw(self, s, off=(0, 0)):
        x, y = int(self.p.x - off[0]), int(self.p.y - off[1])
        draw.line(s, (150, 150, 170), (x, y + self.r), (x, y + self.r + 14), 2)
        draw.circle(s, self.color, (x, y), self.r)
        draw.circle(s, (240, 240, 245), (x - 5, y - 6), 4)
