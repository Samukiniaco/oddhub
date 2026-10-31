"""CaVo — o T: gira 360°, pulo AUTOMÁTICO (ritmo calculado), jato da ponta.

Kit (skins futuras): flap_imp / sink próprios -> o intervalo se recalcula sozinho
via config.hover_interval(). Sem AÇÃO o pulo segura `sink` da gravidade (afunda
devagar e cai do mapa); com AÇÃO o impulso compensa (paira) + amortecimento
lateral p/ mirar estável.
Mundo aberto: sem chão/paredes. Topo/laterais empurram de volta (sem matar);
embaixo do mapa = -1 vida (o game checa e chama force_lose_life).
"""
import math
import os
import random

import pygame

from . import config as C
from .graphics import draw, ViewSurface
from .particles import ChargedBall, Jet, Spark

RESPAWN_TIME = 2.0
INV_ON_RESPAWN = 1.5


def wrap_angle(a):
    """Mantém ângulo em (-180, 180]."""
    return (a + 180.0) % 360.0 - 180.0


def rot_point(pt, pos, angle_deg):
    """Rotaciona ponto local p/ mundo (mesma convenção do desenho: + = horário)."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    x, y = pt
    return (pos[0] + x * ca - y * sa, pos[1] + x * sa + y * ca)


_sprite_cache = {}
_small_fonts = {}


def _font(size):
    if size not in _small_fonts:
        _small_fonts[size] = pygame.font.SysFont("consolas", size)
    return _small_fonts[size]


def load_sprite(path):
    """Carrega sprite uma vez (cache). None se não existir/quebrar."""
    if path in _sprite_cache:
        return _sprite_cache[path]
    img = None
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full = os.path.join(base, path)
        if os.path.isfile(full):
            img = pygame.image.load(full).convert_alpha()
            w, h = img.get_size()
            m = max(w, h)
            if m > C.SPRITE_MAX:
                k = C.SPRITE_MAX / m
                img = pygame.transform.smoothscale(img, (max(1, int(w * k)), max(1, int(h * k))))
    except (pygame.error, OSError):
        img = None
    _sprite_cache[path] = img
    return img


class Player:
    def __init__(self, pos, color, name, idx, sprite_path=None, kit=None):
        self.spawn = pygame.Vector2(pos)
        self.color = color
        self.name = name
        self.idx = idx
        self.sprite_path = sprite_path
        self.sprite = load_sprite(sprite_path) if sprite_path else None
        kit = kit or {}
        self.flap_imp = float(kit.get("flap_imp", C.FLAP_IMP))
        self.sink = float(kit.get("sink", C.SINK_RATIO))
        self.manual_imp = float(kit.get("manual_imp", C.FLAP_MANUAL_IMP))
        self.manual_cd = float(kit.get("manual_cd", C.FLAP_MANUAL_CD))
        self.flap_cost = float(kit.get("manual_cost", C.FLAP_STAM_COST))
        self.auto_interval = C.hover_interval(self.flap_imp, C.GRAV, self.sink)
        self.reset()

    def reset(self):
        self.p = self.spawn.copy()
        self.v = pygame.Vector2(0, 0)
        self.angle = 0.0
        self.flap_cd = 0.0
        self.flap_anim = 0.0
        self._flap_held = False  # edge: segurar não pula, tem que apertar
        self.auto_t = self.auto_interval * 0.5
        self._weak_spent = 0.0  # impulso adiantado do próximo automático, sem voo grátis
        self.stabilizing = False
        self.jet_acc = 0.0
        self.jetting = False
        self.was_jet_held = False
        self.hp = C.HP_MAX
        self.disp_hp = C.HP_MAX  # HP animado (esvanece suave no HUD)
        self.lives = C.LIVES_START
        self.kills = 0
        self.inv = 0.0
        self.dmg_cd = 0.0
        self.dead_t = 0.0
        self.stamina = C.STAM_MAX
        self.exhausted = False
        self.exhaust_t = 0.0
        self.regen_delay = 0.0
        self.charge_cd = 0.0
        self.stam_idle = C.STAM_HIDE_DELAY + C.STAM_FADE_TIME
        self._stam_surface = None

    @property
    def alive(self):
        return self.lives > 0

    @property
    def down(self):
        """HP zerado aguardando renascer (ainda tem vidas)."""
        return self.alive and self.hp <= 0

    @property
    def can_act(self):
        return self.alive and not self.down

    @property
    def charge_ready(self):
        return (self.can_act and not self.exhausted and self.charge_cd <= 0
                and self.stamina >= C.CHARGE_MIN_STAM)

    # ---------- orientação 360° ----------
    def tip_dir(self):
        a = math.radians(self.angle)
        return pygame.Vector2(-math.sin(a), math.cos(a))

    def up_vec(self):
        return -self.tip_dir()

    def tip_pos(self):
        return self.p + self.tip_dir() * C.TIP_DIST

    def aim_at(self, point, dt):
        d = pygame.Vector2(point) - self.p
        if d.length() < 4:
            return
        target = math.degrees(math.atan2(-d.x, d.y))
        diff = wrap_angle(target - self.angle)
        self.angle = wrap_angle(self.angle + diff * min(1.0, dt * C.MOUSE_AIM_SPEED))

    def rotate_keyboard(self, direction, dt):
        self.angle = wrap_angle(self.angle + direction * C.ROT_SPEED_KEY * dt)

    # ---------- stamina ----------
    def start_exhaust(self):
        self.exhausted = True
        self.exhaust_t = random.uniform(C.EXHAUST_MIN, C.EXHAUST_MAX)
        self.jet_acc = 0.0

    # ---------- ações ----------
    def flap(self, sparks):
        """Pulo MANUAL: direcional (p/ onde o topo aponta), rápido de sair.

        Com stamina paga cheio e suprime o automático. Zerado adianta parte
        da próxima batida para cima: freia a queda sem cancelar o automático
        nem empilhar sustentação grátis. Ambos pausam a regeneração.
        """
        if self.flap_cd <= 0 and self.can_act:
            paid = self.stamina >= self.flap_cost
            if paid:
                imp = self.manual_imp
                self.stamina = max(0.0, self.stamina - self.flap_cost)
                self.auto_t = -self.manual_cd
                self._weak_spent = 0.0
                self.v += self.up_vec() * imp
            else:
                # Socorro sempre para cima, independentemente da mira. Adianta
                # parte da batida automática, sem cancelá-la nem somar voo infinito.
                imp = min(self.manual_imp*C.FLAP_WEAK_MUL, max(0.0, self.flap_imp-self._weak_spent))
                self._weak_spent += imp
                self.v.y -= imp
            self.flap_cd = self.manual_cd
            self.regen_delay = max(self.regen_delay, C.STAM_REGEN_DELAY)
            self.flap_anim = 1.0
            if sparks is not None:
                for _ in range(5):
                    sparks.append(Spark(self.p + pygame.Vector2(random.uniform(-14, 14), 10),
                                        pygame.Vector2(random.uniform(-90, 90),
                                                       random.uniform(40, 160)),
                                        0.4, (200, 220, 255), 4))

    def _beat(self, impulse, sparks):
        self.flap_anim = 1.0
        self.v.y -= impulse
        if sparks is not None:
            for _ in range(3):
                sparks.append(Spark(self.p + pygame.Vector2(random.uniform(-14, 14), 10),
                                    pygame.Vector2(random.uniform(-90, 90),
                                                   random.uniform(40, 160)),
                                    0.35, (200, 220, 255), 4))

    def update_jet(self, dt, jet_held, action_held, jets, charged, sparks):
        """Jato + stamina + tiro carregado (segura AÇÃO e SOLTA o jato).

        Retorna a ChargedBall criada, ou None.
        """
        jet_held = bool(jet_held)
        fired = None
        want = jet_held and self.can_act and not self.exhausted
        if want:
            self.stamina -= C.STAM_DRAIN * dt
            self.regen_delay = C.STAM_REGEN_DELAY
            if self.stamina <= 0:
                self.stamina = 0
                self.start_exhaust()
                want = False
        else:
            if self.exhausted:
                self.exhaust_t -= dt
                if self.exhaust_t <= 0:
                    self.exhausted = False
                    self.stamina = C.STAM_MAX
            else:
                self.regen_delay -= dt
                if self.regen_delay <= 0 and self.stamina < C.STAM_MAX:
                    self.stamina = min(C.STAM_MAX, self.stamina + C.STAM_REGEN * dt)
        self.jetting = want
        if want:
            tip = self.tip_pos()
            d = self.tip_dir()
            self.v -= d * C.JET_THRUST * dt
            self.jet_acc += C.JET_EMIT_RATE * dt
            perp = pygame.Vector2(-d.y, d.x)
            while self.jet_acc >= 1.0:
                self.jet_acc -= 1.0
                speed = C.JET_SPEED * random.uniform(0.9, 1.1)
                vel = (d * speed + self.v * C.JET_INHERIT
                       + perp * random.uniform(-C.JET_SPREAD, C.JET_SPREAD))
                jets.append(Jet(tip, vel, self.idx))
            if sparks is not None and random.random() < 0.5:
                sparks.append(Spark(tip, d * 160 + pygame.Vector2(random.uniform(-70, 70),
                                                                  random.uniform(-70, 70)),
                                    0.25, (255, 255, 255), 4, grav=0.0))
        else:
            self.jet_acc = 0.0
        if self.was_jet_held and not jet_held and action_held and self.charge_ready:
            power = self.stamina / C.STAM_MAX
            d = self.tip_dir()
            ball = ChargedBall(self.tip_pos(), d * C.CHARGE_SPEED + self.v * 0.3,
                               self.idx, power)
            charged.append(ball)
            self.v -= d * (C.CHARGE_RECOIL_BASE + C.CHARGE_RECOIL_SCALE * power)
            self.stamina = 0
            self.start_exhaust()
            self.charge_cd = C.CHARGE_CD
            if sparks is not None:
                for _ in range(18):
                    sparks.append(Spark(self.tip_pos(),
                                        d * random.uniform(100, 500) + pygame.Vector2(
                                            random.uniform(-160, 160), random.uniform(-160, 160)),
                                        0.5, random.choice([(255, 255, 255), (170, 210, 255),
                                                            self.color]), 6, grav=100.0))
            fired = ball
        self.was_jet_held = jet_held
        self.charge_cd -= dt
        return fired

    def update_physics(self, dt, sparks=None):
        if self.stamina < C.STAM_MAX or self.exhausted or self.jetting or self.regen_delay > 0:
            self.stam_idle = 0.0
        else:
            self.stam_idle = min(C.STAM_HIDE_DELAY+C.STAM_FADE_TIME, self.stam_idle+dt)
        self.flap_cd -= dt
        self.inv -= dt
        self.dmg_cd -= dt
        self.flap_anim = max(0.0, self.flap_anim - dt * 3.0)
        self.disp_hp += (self.hp - self.disp_hp) * min(1.0, dt * 6.0)
        # pulo AUTOMÁTICO (com AÇÃO o impulso compensa a gravidade: paira)
        if self.can_act:
            self.auto_t += dt
            while self.auto_t >= self.auto_interval:
                self.auto_t -= self.auto_interval
                imp = self.flap_imp / self.sink if self.stabilizing else self.flap_imp
                imp = max(0.0, imp-self._weak_spent)
                self._weak_spent = 0.0
                if imp > 0:
                    self._beat(imp, sparks)
        if self.stabilizing and self.can_act:
            self.v.x *= (1 - min(1.0, C.STABILIZE_DAMP * dt))
            self.v.y *= (1 - min(1.0, C.STABILIZE_DAMP * 0.4 * dt))
        self.v.y += C.GRAV * dt
        drag = C.AIR_DRAG_JETTING if self.jetting else C.AIR_DRAG
        self.v -= self.v * drag * dt
        if self.v.length() > C.MAX_SPEED:
            self.v.scale_to_length(C.MAX_SPEED)
        self.p += self.v * dt
        # topo/laterais: empurra de volta ao centro (sem matar, força cresce p/ fora)
        if self.p.x < 0:
            self.v.x += min(C.SOFT_PUSH_MAX, C.SOFT_PUSH_BASE - self.p.x * C.SOFT_PUSH_GAIN) * dt
        elif self.p.x > C.WORLD_W:
            self.v.x -= min(C.SOFT_PUSH_MAX,
                            C.SOFT_PUSH_BASE + (self.p.x - C.WORLD_W) * C.SOFT_PUSH_GAIN) * dt
        if self.p.y < 0:
            self.v.y += min(C.SOFT_PUSH_MAX, C.SOFT_PUSH_BASE - self.p.y * C.SOFT_PUSH_GAIN) * dt
        # (embaixo do mapa o game tira 1 vida via fell_out)
        if self.down:
            self.dead_t -= dt

    # ---------- dano ----------
    def take_hit(self, dmg, heavy, src_pos, src_vel, sparks):
        """Aplica dano. Retorna True se perdeu uma vida."""
        if not self.can_act:
            return False
        if heavy:
            if self.inv > 0:
                return False
        elif self.inv > 0 or self.dmg_cd > 0:
            return False
        self.hp -= dmg
        self.dmg_cd = C.CHIP_CD
        d = self.p - pygame.Vector2(src_pos)
        if d.length() < 1:
            d = pygame.Vector2(0, -1)
        kb = 200 + dmg * 6
        self.v += d.normalize() * kb + pygame.Vector2(src_vel) * 0.25
        n = 14 if not heavy else 24
        for _ in range(n):
            sparks.append(Spark(self.p, pygame.Vector2(random.uniform(-260, 260),
                                                       random.uniform(-320, 120)),
                                0.6, random.choice([self.color, C.WHITE, (255, 120, 120)]), 5))
        if self.hp <= 0:
            self._lose_life(sparks)
            return True
        if heavy:
            self.inv = C.INV_HEAVY
        return False

    def _lose_life(self, sparks):
        self.hp = 0
        self.lives -= 1
        self.jetting = False
        for _ in range(26):
            sparks.append(Spark(self.p, pygame.Vector2(random.uniform(-340, 340),
                                                       random.uniform(-420, 60)),
                                0.9, self.color, 6))
        if self.alive:
            self.dead_t = RESPAWN_TIME
            self.inv = C.INV_HEAVY

    def fell_out(self, sparks):
        """Caiu do mapa: perde 1 vida na hora. Retorna True se ainda tem jogo."""
        if not self.can_act:
            return False
        self._lose_life(sparks)
        return True

    def respawn_if_ready(self):
        if self.down and self.dead_t <= 0:
            self.hp = C.HP_MAX
            self.disp_hp = C.HP_MAX
            self.p = self.spawn.copy()
            self.v = pygame.Vector2(0, 0)
            self.inv = INV_ON_RESPAWN
            self.angle = 0.0
            self.stamina = C.STAM_MAX
            self.exhausted = False
            self._flap_held = False
            self._weak_spent = 0.0
            self.stam_idle = C.STAM_HIDE_DELAY+C.STAM_FADE_TIME
            return True
        return False

    # ---------- desenho ----------
    def draw(self, s, off=(0, 0), show_stamina=True):
        if not self.alive:
            return
        px, py = self.p.x - off[0], self.p.y - off[1]
        if self.down:
            if int(self.dead_t * 8) % 2 == 0:
                draw.circle(s, (120, 120, 140), (int(px), int(py)), 10)
            return
        if self.sprite is not None:
            rot = pygame.transform.rotate(self.sprite, -self.angle)
            s.blit(rot, rot.get_rect(center=(int(px), int(py))))
            tip = self.tip_pos()
            tx, ty = int(tip.x - off[0]), int(tip.y - off[1])
            if self.jetting:
                draw.circle(s, (255, 255, 255), (tx, ty), 10)
            draw.circle(s, C.YELLOW, (tx, ty), 3)
            if show_stamina:
                self._draw_stam_ring(s, off)
            return
        blink = self.inv > 0 and int(self.inv * 12) % 2 == 0
        col = (90, 100, 120) if blink else self.color

        def rot(pt):
            rx, ry = rot_point(pt, (self.p.x, self.p.y), self.angle)
            return (rx - off[0], ry - off[1])

        flap = math.sin(self.flap_anim * math.pi * 3) * 10 * max(0.25, self.flap_anim)
        for side in (-1, 1):
            base = rot((side * 6, 2))
            tip = rot((side * (26 + flap), -8 - flap * 0.6))
            back = rot((side * 8, -6))
            draw.polygon(s, C.WHITE, [base, tip, back])

        hat = [rot((-22, -14)), rot((22, -14)), rot((22, -4)), rot((-22, -4))]
        stem = [rot((-7, -4)), rot((7, -4)), rot((7, 20)), rot((-7, 20))]
        draw.polygon(s, col, hat)
        draw.polygon(s, col, stem)
        draw.polygon(s, C.WHITE, hat, 2)
        draw.polygon(s, C.WHITE, stem, 2)
        tip = self.tip_pos()
        tx, ty = int(tip.x - off[0]), int(tip.y - off[1])
        if self.jetting:
            draw.circle(s, (255, 255, 255), (tx, ty), 10)
            draw.circle(s, (255, 240, 180), (tx, ty), 7)
        draw.circle(s, (40, 42, 60), (tx, ty), 6)
        draw.circle(s, C.YELLOW, (tx, ty), 3)
        ex, ey = rot((0, -9))
        draw.circle(s, (20, 22, 35), (int(ex), int(ey)), 3)
        if show_stamina:
            self._draw_stam_ring(s, off)

    def _draw_stam_ring(self, s, off):
        """Indicador pequeno ao lado; preserva arco, cores e contagem da exaustão."""
        alpha = self.stamina_alpha
        if not self.can_act or alpha <= 0:
            return
        zoom = s.scale if isinstance(s, ViewSurface) else 1.0
        x, y = self.p.x-off[0], self.p.y-off[1]
        cx, cy = x+C.STAM_INDICATOR_OFFSET[0], y+C.STAM_INDICATOR_OFFSET[1]
        clip = s.get_clip()
        if cx+C.STAM_INDICATOR_RADIUS > clip.right:
            cx = x-C.STAM_INDICATOR_OFFSET[0]
        center = s.point((cx, cy)) if isinstance(s, ViewSurface) else (round(cx), round(cy))
        target = s.surface if isinstance(s, ViewSurface) else s
        R = max(3, round(C.STAM_INDICATOR_RADIUS*zoom))
        font = _font(max(6, round(C.STAM_INDICATOR_FONT*zoom)))
        size = (R*2+8, R*2+font.get_height()+12)
        if self._stam_surface is None or self._stam_surface.get_size() != size:
            self._stam_surface = pygame.Surface(size, pygame.SRCALPHA)
        image = self._stam_surface
        image.fill((0, 0, 0, 0))
        cx, cy = size[0]//2, R+3
        draw.circle(image, (40, 46, 70), (cx, cy), R, max(1, round(zoom)))
        if self.exhausted:
            pulse = 0.6 + 0.4 * math.sin(pygame.time.get_ticks() * 0.012)
            draw.circle(image, (255, 90, 90), (cx, cy), R, max(1, round(C.STAM_INDICATOR_WIDTH*pulse*zoom)))
            img = font.render(f"{self.exhaust_t:.0f}s", True, (255, 130, 130))
            image.blit(img, img.get_rect(center=(cx, cy+R+font.get_height()//2+2)))
        else:
            frac = max(0.0, min(1.0, self.stamina / C.STAM_MAX))
            if frac > 0:
                col = (150, 235, 255) if frac > 0.25 else (255, 170, 60)
                draw.arc(image, col, (cx-R, cy-R, R*2, R*2),
                         -math.pi/2, -math.pi/2+math.pi*2*frac,
                         max(1, round(C.STAM_INDICATOR_WIDTH*zoom)))
        image.set_alpha(alpha)
        target.blit(image, (center[0]-cx, center[1]-cy))

    @property
    def stamina_alpha(self):
        if self.stamina < C.STAM_MAX or self.exhausted or self.jetting or self.regen_delay > 0:
            return 255
        remaining = 1-max(0.0, self.stam_idle-C.STAM_HIDE_DELAY)/C.STAM_FADE_TIME
        return round(255*max(0.0, min(1.0, remaining)))
