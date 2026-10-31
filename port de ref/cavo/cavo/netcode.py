"""CaVo — netcode: buffer de estados remotos, interpolação e extrapolação.

O mesmo Ghost serve o relay (WebSocket) e a nuvem (Firebase): guarda as
amostras do oponente com o instante de CHEGADA e devolve o estado no
instante de render (agora - atraso). O atraso se adapta à irregularidade
das amostras: se a rede engasga, o buffer segura mais tempo em vez de
pular. Se o buffer secar (oponente calado), extrapola pela velocidade
por um instante curto.
"""
import collections
import time

from . import config as C


def shortest_angle(a, b):
    """Diferença angular mínima de a até b (graus, -180..180)."""
    return (b - a + 180.0) % 360.0 - 180.0


class Ghost:
    """Buffer do oponente: (chegada, estado) -> estado renderizado."""

    def __init__(self, base_delay=None, min_delay=None, max_delay=None,
                 max_extrap=None, expected_hz=None):
        self.snaps = collections.deque(maxlen=C.NET_SNAP_MAX)
        self.base_delay = C.NET_DELAY_BASE if base_delay is None else base_delay
        self.min_delay = C.NET_DELAY_MIN if min_delay is None else min_delay
        self.max_delay = C.NET_DELAY_MAX if max_delay is None else max_delay
        self.max_extrap = C.NET_EXTRAP_MAX if max_extrap is None else max_extrap
        self.expected = 1.0 / (expected_hz or C.NET_SEND_HZ)
        self.delay = self.base_delay
        self._late = 0.0
        self._age = 0.0
        self._last_arrival = 0.0

    # ---------- escrita ----------
    def push(self, state, now=None):
        """Guarda uma amostra e reajusta o atraso adaptativo."""
        now = time.time() if now is None else now
        if self._last_arrival:
            late = (now - self._last_arrival) - self.expected
            if late > 0:
                self._late = min(0.6, self._late * 0.85 + late * 0.15)
        self._last_arrival = now
        self.snaps.append((now, state))
        self.delay = max(self.min_delay,
                         min(self.max_delay, self.base_delay + 1.5 * self._late))
        return self.delay

    def _tune(self, now):
        """O atraso segue a idade real da última amostra.

        Se o render fica atrás demais do dado, o buffer seca e o fantasma
        sai extrapolando (sobe e desce); se fica adiantado, o oponente
        aparece no futuro. Atraso = idade do dado + meio intervalo: aí
        sempre há duas amostras para interpolar.
        """
        if not self.snaps:
            return
        age = now - self.snaps[-1][0]
        self._age += (age - self._age) * 0.15
        want = self._age + 0.9 * self.expected
        want = max(self.min_delay, min(self.max_delay, want))
        self.delay += (want - self.delay) * 0.25
        self.delay = max(self.min_delay, min(self.max_delay, self.delay))

    def clear(self):
        self.snaps.clear()
        self._late = 0.0
        self._age = 0.0
        self._last_arrival = 0.0
        self.delay = self.base_delay

    # ---------- leitura ----------
    def _interp(self, older, newer, k):
        a, b = older[1], newer[1]
        out = {}
        for f in ("x", "y", "vx", "vy"):
            try:
                av, bv = float(a.get(f, 0)), float(b.get(f, 0))
            except (TypeError, ValueError):
                av = bv = 0.0
            out[f] = av + (bv - av) * k
        try:
            a0, a1 = float(a.get("a", 0)), float(b.get("a", 0))
            out["a"] = a0 + shortest_angle(a0, a1) * k
        except (TypeError, ValueError):
            out["a"] = 0.0
        for f in ("jet", "stam"):
            out[f] = b.get(f, a.get(f, 0))
        out["seq"] = b.get("seq", a.get("seq", 0))
        return out

    def _extrap(self, newest, ahead):
        """Segue pela velocidade quando o buffer secou (pouco, senão vira teletransporte)."""
        out = dict(newest[1])
        try:
            out["x"] = float(newest[1].get("x", 0)) + float(newest[1].get("vx", 0)) * ahead
            out["y"] = float(newest[1].get("y", 0)) + float(newest[1].get("vy", 0)) * ahead
        except (TypeError, ValueError):
            pass
        out["ahead"] = ahead
        return out

    def sample(self, now=None):
        """Estado do oponente para o instante (agora - delay). None se não há nada."""
        if not self.snaps:
            return None
        now = time.time() if now is None else now
        self._tune(now)
        if len(self.snaps) == 1:
            only = self.snaps[0]
            ahead = min(now - only[0], self.max_extrap)
            out = self._extrap(only, ahead) if ahead > 0 else dict(only[1])
            out["ahead"] = max(0.0, ahead)
            return out
        target = now - self.delay
        older, newer = self.snaps[0], self.snaps[-1]
        for i in range(len(self.snaps) - 1):
            if self.snaps[i][0] <= target <= self.snaps[i + 1][0]:
                older, newer = self.snaps[i], self.snaps[i + 1]
                break
        else:
            # alvo depois da amostra mais nova: extrapola (ou segura a mais nova)
            ahead = min(target - newer[0], self.max_extrap)
            if ahead <= 0:
                ahead = min(newer[0] - target, self.max_extrap)
                if ahead > 0:
                    out = self._extrap(newer, -ahead)
                    out["ahead"] = -ahead
                    return out
                out = dict(newer[1])
                out["ahead"] = 0.0
                return out
            out = self._extrap(newer, ahead)
            out["ahead"] = ahead
            return out
        span = newer[0] - older[0]
        k = 0.0 if span <= 0 else max(0.0, min(1.0, (target - older[0]) / span))
        out = self._interp(older, newer, k)
        out["ahead"] = 0.0
        return out

    def age(self, now=None):
        """Idade da amostra mais nova (segundos)."""
        if not self.snaps:
            return 999.0
        now = time.time() if now is None else now
        return now - self.snaps[-1][0]
