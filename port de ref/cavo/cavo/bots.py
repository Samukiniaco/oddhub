"""CaVo — cérebro dos bots: máquina de estados honesta com a mesma física sua.

Modos: chase (ponta p/ trás, jato empurra até o alvo), fight (ponta NO alvo,
rajadas + recuo de verdade), climb (perigo/ exausto: ponta p/ baixo e sobe),
idle (pairar com AÇÃO). Tiro carregado quando colado + cheio. Mira com erro e
antecipação por skill. Gerencia stamina (reserva) p/ não se matar à toa.
"""
import math
import random

import pygame

from . import config as C
from .input import Intent


def tip_angle_for(dx, dy):
    """Ângulo da ponta que aponta p/ (dx, dy)."""
    return math.degrees(math.atan2(-dx, dy))


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


class Brain:
    def __init__(self, skill="normal"):
        self.cfg = C.BOT_SKILLS[skill]
        self.skill = skill
        self.noise = 0.0
        self._chg = 0.0  # timer do tiro carregado
        self._burst = 0.0  # rajada do fight (0.35s ligado / 0.45s pausa)
        self._flap_t = 0.0
        self._charge_wait = random.uniform(*C.BOT_CHARGE_INITIAL_DELAY)
        self._charge_target = None
        self._release_charge = False
        self._recovering = False
        self._refuelling = False

    def _steer(self, me, target_angle):
        diff = wrap(target_angle - me.angle)
        return max(-1.0, min(1.0, diff / 25.0))

    def decide(self, me, foes, dt):
        self._flap_t = max(0.0, self._flap_t-dt)
        self._charge_wait = max(0.0, self._charge_wait-dt)
        self._release_charge = False
        out = self._decide(me, foes, dt)
        # AÇÃO também dispara a bolona na soltura. Rajada comum não é carga!
        if me.was_jet_held and not out.jet and not self._release_charge:
            out.action = False
        request = out.flap and me.can_act and self._flap_t <= 0
        out.flap = bool(request)
        if request:
            self._flap_t = C.BOT_FLAP_INTERVAL
        return out

    def _decide(self, me, foes, dt):
        alive = [f for f in foes if f is not me and f.alive and f.hp > 0]
        reserve = self.cfg["reserve"]
        self._burst += dt
        low = me.p.y+max(0, me.v.y)*C.BOT_RECOVERY_LOOKAHEAD > C.WORLD_H-C.BOT_RECOVERY_MARGIN
        if not alive:
            self._chg = 0.0
            return Intent(flap=False, jet=False, action=True)  # paira
        tgt = min(alive, key=lambda f: (f.p - me.p).length())
        dist = (tgt.p - me.p).length()
        self.noise += random.uniform(-1, 1) * 40 * dt
        self.noise *= (1 - min(1, dt * 2))
        if low:
            self._recovering = True
        elif me.p.y <= C.BOT_RECOVERY_EXIT_Y and me.v.y < C.BOT_CHARGE_MAX_FALL:
            self._recovering = False
        if me.exhausted:
            self._chg = 0.0
            # Usa o mesmo socorro/estabilização disponível ao jogador, sem jato.
            return Intent(rotate=self._steer(me, 0.0),
                          flap=me.v.y > C.BOT_CHARGE_MAX_FALL,
                          jet=False,
                          action=True)
        if self._recovering:
            self._chg = 0.0
            if me.stamina <= reserve:
                self._refuelling = True
            elif me.stamina >= reserve+C.BOT_REFUEL_BUFFER:
                self._refuelling = False
            aligned_up = abs(wrap(me.angle)) < C.BOT_RECOVERY_ALIGN
            # perigo mas com stamina: ponta p/ baixo, jato + estabiliza p/ subir
            return Intent(rotate=self._steer(me, 0.0),
                          flap=me.v.y > 250 and aligned_up and not self._refuelling,
                          jet=not self._refuelling and aligned_up,
                          action=True)
        if dist > 420:
            self._chg = 0.0
            # chase: ponta p/ TRÁS (jato empurra até o alvo). Sobe SÓ se estiver
            # abaixo do alvo (viés fixo fazia os bots fugirem p/ o topo p/ sempre).
            # Jato só de longe: perto, plana no flap e chega com stamina p/ lutar.
            d = tgt.p - me.p
            n = d.length() or 1.0
            mx, my = d.x / n, d.y / n
            if me.p.y > tgt.p.y - 100:
                my -= 0.35
            n2 = math.hypot(mx, my) or 1.0
            back = tip_angle_for(-mx / n2, -my / n2)
            # guarda stamina p/ chegar lutando (reserva + 25) e jateia em
            # rajadas: saldo positivo, persegue p/ sempre sem exaurir
            cruise = (self._burst % 1.0) < 0.4
            return Intent(rotate=self._steer(me, back),
                          flap=me.v.y > 200,
                          jet=dist > 520 and cruise and me.stamina > reserve + 25,
                          action=False)
        # fight: ponta NO alvo com antecipação + erro
        lead = dist / C.JET_SPEED * self.cfg["lead"]
        ax = tgt.p.x + tgt.v.x * lead
        ay = tgt.p.y + tgt.v.y * lead
        err = self.cfg["aim_err"] * dist / 500.0
        ax += -math.sin(math.radians(self.noise)) * err * 10
        ay += math.cos(math.radians(self.noise)) * err * 10
        want = tip_angle_for(ax - me.p.x, ay - me.p.y)
        aligned = abs(wrap(want - me.angle)) < 12.0
        # carregado SÓ colado + cheio (gastar tudo de longe é burrice)
        if self._charge_target != tgt.idx:
            self._chg = 0.0
            self._charge_target = tgt.idx
        safe = (me.p.y < C.WORLD_H-C.BOT_CHARGE_SAFE_HEIGHT and
                me.v.y < C.BOT_CHARGE_MAX_FALL and tgt.inv <= 0)
        enough = me.stamina >= C.BOT_CHARGE_STAMINA or (self._chg > 0 and me.charge_ready)
        if (dist < C.BOT_CHARGE_DISTANCE and enough and aligned and safe and
                self._charge_wait <= 0 and me.charge_cd <= 0):
            self._chg += dt
            if self._chg >= C.BOT_CHARGE_PREPARE:
                self._chg = 0.0
                self._release_charge = True
                self._charge_wait = random.uniform(*C.BOT_CHARGE_INTERVALS[self.skill])
                return Intent(rotate=self._steer(me, want), flap=False,
                              jet=False, action=True)  # SOLTA = bolona
            return Intent(rotate=self._steer(me, want), flap=False,
                          jet=True, action=True)
        self._chg = 0.0
        burst_on = (self._burst % 0.8) < 0.35  # rajada curta: menos fling, menos burn
        return Intent(rotate=self._steer(me, want),
                      flap=me.v.y > 200,
                      jet=aligned and burst_on and me.stamina > reserve,
                      action=True)
