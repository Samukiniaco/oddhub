"""CaVo — partículas: faíscas ambientes e o JATO branco contínuo.

O jato é tiro E rastro: cada partícula tem gravidade, quica um pouco
e machuca (balão estoura, T adversário toma knockback).
"""
import random

import pygame

from . import config as C
from .graphics import draw


class Spark:
    """Faisquinha decorativa (flap, explosão, quique do jato)."""

    def __init__(self, p, v, life, color, size, grav=500.0):
        self.p = pygame.Vector2(p)
        self.v = pygame.Vector2(v)
        self.life = life
        self.max = life
        self.color = color
        self.size = size
        self.grav = grav

    def update(self, dt):
        self.life -= dt
        self.v.y += self.grav * dt
        self.p += self.v * dt
        return self.life > 0

    def draw(self, s, off=(0, 0)):
        a = max(0.0, self.life / self.max)
        draw.circle(s, self.color, (int(self.p.x - off[0]), int(self.p.y - off[1])),
                           max(1, int(self.size * a)))


class Jet:
    """Um pingo do jato branco. Sai da ponta, tem gravidade, deixa rastro."""

    def __init__(self, p, v, owner):
        self.p = pygame.Vector2(p)
        self.v = pygame.Vector2(v)
        self.owner = owner
        self.max = C.JET_LIFE + random.uniform(-C.JET_LIFE_JITTER, C.JET_LIFE_JITTER)
        self.life = self.max
        self.age = 0.0
        self.size = C.JET_SIZE + random.uniform(-1.5, 1.5)
        self.bounces = 0

    def update(self, dt):
        self.life -= dt
        self.age += dt
        self.v.y += C.JET_GRAV * dt
        self.v -= self.v * C.JET_DRAG * dt
        self.p += self.v * dt
        # sem chão/paredes: o rastro morre ao sair longe do mundo
        m = 400.0
        inside = (-m < self.p.x < C.WORLD_W + m) and (-m < self.p.y < C.WORLD_H + m)
        return self.life > 0 and inside

    def draw(self, s, off=(0, 0)):
        x, y = int(self.p.x - off[0]), int(self.p.y - off[1])
        fade = max(0.0, self.life / self.max)
        # halo esfumaçado + núcleo branco (constante e branco, como pedido)
        r_halo = int(self.size * (0.6 + fade))
        halo = (int(120 + 80 * fade), int(150 + 70 * fade), int(190 + 50 * fade))
        draw.circle(s, halo, (x, y), max(1, r_halo))
        r_core = max(1, int(self.size * 0.55 * fade) + 1)
        draw.circle(s, (255, 255, 255), (x, y), r_core)


class ChargedBall:
    """A BOLONA do tiro carregado: gasta toda a stamina, recuo forte, dano alto."""

    def __init__(self, p, v, owner, power):
        self.p = pygame.Vector2(p)
        self.v = pygame.Vector2(v)
        self.owner = owner
        self.power = max(0.0, min(1.0, power))
        self.size = 10 + 10 * self.power
        self.dmg = C.CHARGE_DMG_BASE + C.CHARGE_DMG_SCALE * self.power
        self.life = C.CHARGE_LIFE
        self.t = 0.0
        self.bounces = 0

    def update(self, dt):
        import math
        self.t += dt
        self.life -= dt
        self.v.y += C.JET_GRAV * C.CHARGE_GRAV_MUL * dt
        self.p += self.v * dt
        m = 400.0
        inside = (-m < self.p.x < C.WORLD_W + m) and (-m < self.p.y < C.WORLD_H + m)
        return self.life > 0 and inside

    def draw(self, s, off=(0, 0)):
        import math
        pulse = 1.0 + 0.1 * math.sin(self.t * 20)
        r = int(self.size * pulse)
        x, y = int(self.p.x - off[0]), int(self.p.y - off[1])
        draw.circle(s, (90, 140, 255), (x, y), r + 8)
        draw.circle(s, (170, 210, 255), (x, y), r + 3)
        draw.circle(s, (255, 255, 255), (x, y), max(2, r - 4))
