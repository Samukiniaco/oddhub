"""CaVo — partida online na nuvem (Firebase RTDB): sem relay, sem processo extra.

COMO FUNCIONA (1x1):
  * cada lado escreve o PRÓPRIO estado (PATCH) ~20Hz e lê a subárvore da
    partida (GET/poll) ~30Hz. O SSE do RTDB só descarrega ~1x/s, então
    jogo de verdade não pode usar stream: quem escreve, quem lê.
  * quem acerta manda um PEDIDO DE DANO (claim). O HOST é o árbitro: confere
    alcance, cooldown e invencibilidade e escreve o HP/vidas oficial de cada
    lado. Ninguém mexe no HP dos outros.
  * o claim também é aviso rápido: quem levou o tiro sente na hora (o HP
    oficial chega depois e corrige se o tiro foi inválido).
  * o host que cair limpa a subárvore; o outro lado percebe e volta ao menu.

API igual à do relay (cavo/online.py): send_inputs / send_hit / send_fell /
poll_events / interp_foe / ping / alive / close. O jogo não sabe a diferença.
"""
import collections
import math
import threading
import time

from . import config as C
from . import net
from .netcode import Ghost


class FbError(Exception):
    """Erro do Firebase durante a partida (permissão, rede, 404...)."""

    def __init__(self, msg, fatal=False):
        super().__init__(msg)
        self.fatal = fatal


class HttpTransport:
    """Fala com o RTDB por HTTPS (uma sessão persistente por thread)."""

    def __init__(self, timeout=None):
        self.timeout = C.NET_TIMEOUT if timeout is None else timeout
        self._local = threading.local()

    def _session(self):
        s = getattr(self._local, "s", None)
        if s is None:
            import requests
            s = requests.Session()
            self._local.s = s
        return s

    def _request(self, method, path, data=None):
        url = net.fb_url(path)
        try:
            r = self._session().request(method, url, json=data, timeout=self.timeout)
        except Exception as e:
            raise FbError(f"rede: {e}")
        if r.status_code in (200, 204):
            if method == "GET":
                try:
                    return r.json()
                except ValueError:
                    return None
            return True
        if r.status_code in (401, 403):
            raise FbError("sem permissão no Firebase (regras da sala)", fatal=True)
        if r.status_code == 404:
            raise FbError("sala sumiu do Firebase", fatal=True)
        raise FbError(f"Firebase HTTP {r.status_code}")

    def write(self, path, data):
        """PATCH (mescla) — o estado e os pedidos de dano."""
        return self._request("PATCH", path, data)

    def read(self, path):
        return self._request("GET", path)

    def remove(self, path):
        return self._request("DELETE", path)


class FbSession:
    """Sessão de partida na nuvem. Mesma API da OnlineSession (relay)."""

    def __init__(self, code, you, name, transport=None, arbiter=False, base=None):
        self.code = str(code).upper()
        self.you = int(you)
        self.foe = 1 - self.you
        self.name = name
        self.arbiter = bool(arbiter)
        self.transport = transport or HttpTransport()
        self.clean_base = f"rooms/{self.code}/match"
        self.compat_base = f"rooms/{self.code}/settings/match"
        self.base = base or self._pick_base()
        # --- estado local ---
        self.ghost = Ghost(base_delay=C.NET_DELAY_CLOUD)
        self.events = collections.deque(maxlen=64)
        self.rtt = 0.0
        self._alive = True
        self._lock = threading.Lock()
        self._seq = 0
        self._claim_seq = 0
        self._pending = None
        self._wake = threading.Event()
        self._inflight = 0
        self._fails = 0
        self._last_error = ""
        self._seen_data = False
        self._foe_seen = 0.0
        self._states = {0: None, 1: None}
        self._hist = {0: collections.deque(maxlen=96), 1: collections.deque(maxlen=96)}
        self._state_seq = {0: -1, 1: -1}
        self._hp_seq = {0: -1, 1: -1}        # maior seq de hp já lida
        self._hp_write = {0: 0, 1: 0}        # contador de escrita do árbitro
        self._claim_seen = {0: 0, 1: 0}
        self._cd = {0: 0.0, 1: 0.0}
        self._meta = {}
        # HP oficial (o árbitro escreve) + previsões ainda não confirmadas
        self.hp = {0: {"hp": C.HP_MAX, "lives": C.LIVES_START, "inv": 0.0},
                   1: {"hp": C.HP_MAX, "lives": C.LIVES_START, "inv": 0.0}}
        self.pred = {0: {}, 1: {}}           # seq do pedido -> dano previsto
        self._resolved = {0: set(), 1: set()}
        self._threads = []

    # ---------- caminhos ----------
    def _pick_base(self):
        """Caminho da partida: o limpo (regras nível 2) ou settings/match (nível 1)."""
        try:
            self.transport.write(f"{self.clean_base}/probe", {"v": 1})
            self.transport.remove(f"{self.clean_base}/probe")
            return self.clean_base
        except Exception:
            return self.compat_base

    # ---------- ciclo de vida ----------
    def start(self):
        if self.arbiter:
            self._init_match()
        self._poll_workers = 0
        for _ in range(C.NET_WORKERS):
            self._spawn_poller()
        t = threading.Thread(target=self._write_loop, daemon=True)
        t.start()
        self._threads.append(t)
        return self

    def _spawn_poller(self):
        self._poll_workers += 1
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()
        self._threads.append(t)

    def _init_match(self):
        """Árbitro abre a partida: HP/vidas oficiais dos dois lados."""
        now = int(time.time() * 1000)
        # limpa sobra de partida anterior (estado e pedidos velhos) em paralelo
        def limpa(nome):
            try:
                self.transport.remove(f"{self.base}/{nome}")
            except FbError:
                pass
        limpadas = [threading.Thread(target=limpa, args=(nome,), daemon=True)
                    for nome in ("state0", "state1", "claim0", "claim1")]
        for t in limpadas:
            t.start()
        for t in limpadas:
            t.join(timeout=3.0)
        for side in (0, 1):
            self.hp[side] = {"hp": C.HP_MAX, "lives": C.LIVES_START, "inv": 0.0}
            seq = self._next_hp_seq(side)
            try:
                self.transport.write(f"{self.base}/hp{side}", {
                    "hp": C.HP_MAX, "lives": C.LIVES_START, "inv": 0.0,
                    "seq": seq, "last_claim": 0, "ts": now})
                self._hp_seq[side] = seq
            except FbError as e:
                raise FbError(f"não consegui abrir a partida: {e}", fatal=True)
        try:
            self.transport.write(f"{self.base}/meta", {
                "phase": "playing", "winner": -1, "started": now,
                "host": self.name if self.you == 0 else ""})
        except FbError as e:
            raise FbError(f"não consegui abrir a partida: {e}", fatal=True)

    @property
    def alive(self):
        return self._alive

    def close(self):
        self._alive = False
        self._wake.set()
        if self.arbiter:
            # o host limpa a partida (o outro lado percebe e volta ao menu).
            # Em background: não segura o jogo na hora de sair.
            def limpa():
                try:
                    self.transport.remove(self.base)
                except Exception:
                    pass
            threading.Thread(target=limpa, daemon=True).start()

    # ---------- escrita (jogo -> nuvem) ----------
    def send_inputs(self, seq, pl):
        """Estado do meu T (o jogo chama a 20Hz)."""
        with self._lock:
            self._pending = {
                "seq": int(seq), "ts": int(time.time() * 1000),
                "x": float(pl.p.x), "y": float(pl.p.y),
                "vx": float(pl.v.x), "vy": float(pl.v.y),
                "a": float(pl.angle), "jet": bool(pl.jetting),
                "stam": float(pl.stamina),
            }
        self._wake.set()

    def send_hit(self, dmg, heavy, x=None, y=None):
        """Pedi dano no oponente (o árbitro decide).

        x/y são ONDE o atirador acertou (o ponto do fantasma que ele viu).
        O árbitro confere esse ponto contra o histórico de posição da
        vítima: com a rede lenta, o fantasma já é velho, e o tiro tem que
        ser julgado onde a vítima ESTAVA, não onde está agora.
        """
        seq = self._next_claim()
        self.pred[self.foe][seq] = float(dmg)
        claim = {"seq": seq, "kind": "hit", "dmg": float(dmg),
                 "heavy": bool(heavy), "ts": int(time.time() * 1000)}
        if x is not None and y is not None:
            claim["x"] = float(x)
            claim["y"] = float(y)
        self._write_claim(claim)

    def send_fell(self):
        """Caiu do mapa: pede para perder uma vida."""
        seq = self._next_claim()
        self._write_claim({"seq": seq, "kind": "fell", "ts": int(time.time() * 1000)})

    def ping(self):
        """O RTT sai do polling; nada a fazer aqui."""
        return self.rtt

    def _next_claim(self):
        with self._lock:
            self._claim_seq += 1
            return self._claim_seq

    def _write_claim(self, claim):
        slot = "a" if claim["seq"] % C.NET_CLAIM_SLOTS == 0 else "b"
        try:
            self.transport.write(f"{self.base}/claim{self.you}/{slot}", claim)
        except FbError as e:
            self._last_error = str(e)
            if e.fatal:
                self._alive = False

    # ---------- leitura (nuvem -> jogo) ----------
    def poll_events(self):
        out = list(self.events)
        self.events.clear()
        return out

    def hp_of(self, side):
        """HP efetivo: oficial menos o que ainda não foi confirmado."""
        auth = float(self.hp[side]["hp"])
        pend = sum(self.pred[side].values())
        return max(0.0, auth - pend)

    def lives_of(self, side):
        return int(self.hp[side]["lives"])

    def interp_foe(self):
        """Fantasma do oponente: posição interpolada + HP oficial."""
        g = self.ghost.sample()
        if not g:
            return None
        out = dict(g)
        out["hp"] = self.hp_of(self.foe)
        out["lives"] = self.lives_of(self.foe)
        out["ok"] = True
        out["fresh"] = (time.time() - self._foe_seen) < 1.5
        return out

    # ---------- threads ----------
    def _write_loop(self):
        from concurrent.futures import ThreadPoolExecutor
        pool = ThreadPoolExecutor(max_workers=C.NET_WORKERS + 2)
        try:
            while self._alive:
                state = self._take_pending()
                if state is None:
                    self._wake.wait(0.05)
                    self._wake.clear()
                    continue
                if self._inflight >= C.NET_WORKERS + 2:
                    continue  # saturado: o estado mais novo vem logo
                self._inflight += 1
                pool.submit(self._do_write, state)
                time.sleep(1.0 / C.NET_SEND_HZ)
        finally:
            pool.shutdown(wait=False)

    def _take_pending(self):
        with self._lock:
            state, self._pending = self._pending, None
        return state

    def _do_write(self, state):
        try:
            slot = "a" if state["seq"] % C.NET_CLAIM_SLOTS == 0 else "b"
            self.transport.write(f"{self.base}/state{self.you}/{slot}", state)
            self._fails = 0
        except FbError as e:
            self._last_error = str(e)
            self._fails += 1
            if e.fatal:
                self._alive = False
        finally:
            self._inflight -= 1

    def _poll_loop(self):
        while self._alive:
            t = time.time()
            try:
                data = self.transport.read(self.base)
            except FbError as e:
                self._last_error = str(e)
                self._fails += 1
                if e.fatal or self._fails >= C.NET_GIVEUP:
                    self._alive = False
                    self.events.append({"t": "closed", "why": str(e)})
                time.sleep(0.4)
                continue
            self._fails = 0
            rtt = time.time() - t
            self.rtt = rtt if self.rtt <= 0 else self.rtt * 0.8 + rtt * 0.2
            # link lento: abre mais leitores para não perder amostras
            if self.rtt > 0.25 and self._poll_workers < C.NET_WORKERS_MAX:
                self._spawn_poller()
            if data:
                self._seen_data = True
                self._ingest(data)
            elif self._seen_data:
                # a subárvore sumiu (o host limpou a partida)
                self._alive = False
                self.events.append({"t": "closed", "why": "sala sumiu"})
                continue
            if self._foe_seen and time.time() - self._foe_seen > C.NET_LOST_SECONDS:
                self._alive = False
                self.events.append({"t": "closed", "why": "o outro lado caiu"})
                continue
            time.sleep(0.004)

    # ---------- dados vindos da nuvem ----------
    def _ingest(self, data):
        now = time.time()
        for side in (0, 1):
            node = data.get(f"hp{side}")
            if isinstance(node, dict):
                self._ingest_hp(side, node)
        for side in (0, 1):
            st = data.get(f"state{side}")
            if isinstance(st, dict):
                self._ingest_state(side, st, now)
        for side in (0, 1):
            cl = data.get(f"claim{side}")
            if isinstance(cl, dict):
                for slot in cl.values():
                    if isinstance(slot, dict):
                        self._ingest_claim(side, slot)
        meta = data.get("meta")
        if isinstance(meta, dict):
            self._ingest_meta(meta)

    def _ingest_state(self, side, node, now):
        best = None
        for slot in node.values():
            if isinstance(slot, dict):
                if best is None or slot.get("seq", -1) > best.get("seq", -1):
                    best = slot
        if best is None:
            return
        try:
            seq = int(best.get("seq", -1))
        except (TypeError, ValueError):
            return
        if seq <= self._state_seq[side]:
            return
        self._state_seq[side] = seq
        self._states[side] = best
        try:
            self._hist[side].append((now, float(best.get("x", 0)), float(best.get("y", 0))))
        except (TypeError, ValueError):
            pass
        if side == self.foe:
            self.ghost.push(best, now)
            self._foe_seen = now

    def _ingest_hp(self, side, node):
        try:
            seq = int(node.get("seq", 0))
        except (TypeError, ValueError):
            return
        if seq <= self._hp_seq[side]:
            return
        self._hp_seq[side] = seq
        prev = self.hp[side]
        hp = float(node.get("hp", prev["hp"]))
        lives = int(node.get("lives", prev["lives"]))
        inv = float(node.get("inv", 0.0))
        last_claim = int(node.get("last_claim", 0) or 0)
        self.hp[side] = {"hp": hp, "lives": lives, "inv": inv}
        # a previsão do pedido resolvido (confirmado OU recusado) sai da fila
        if last_claim:
            self.pred[side].pop(last_claim, None)
            self._resolved[side].add(last_claim)
        lost = lives < int(prev["lives"])
        if hp < float(prev["hp"]) or lost:
            self.events.append({"t": "dmg", "side": side, "hp": hp, "lives": lives,
                                "lost": lost, "heavy": bool(node.get("heavy", False)),
                                "dmg": float(node.get("dmg", 0.0))})
            if lost:
                self.events.append({"t": "reset", "side": side, "hp": hp, "lives": lives})

    def _ingest_claim(self, side, claim):
        try:
            seq = int(claim.get("seq", 0))
        except (TypeError, ValueError):
            return
        if seq <= self._claim_seen[side]:
            return
        self._claim_seen[side] = seq
        kind = claim.get("kind", "hit")
        if kind == "fell":
            if self.arbiter:
                self._arbitrate_fell(side, seq)
            return
        try:
            dmg = float(claim.get("dmg", C.CHIP_DMG))
        except (TypeError, ValueError):
            dmg = C.CHIP_DMG
        heavy = bool(claim.get("heavy"))
        victim = 1 - side
        aim = None
        try:
            if "x" in claim and "y" in claim:
                aim = (float(claim["x"]), float(claim["y"]))
        except (TypeError, ValueError):
            aim = None
        if self.arbiter:
            self._arbitrate_hit(side, seq, dmg, heavy, aim)
        elif side != self.you:
            # aviso rápido pra quem levou o tiro (a confirmação oficial vem depois)
            if seq not in self._resolved[victim]:
                self.pred[victim][seq] = dmg
            self.events.append({"t": "pred", "side": victim, "dmg": dmg, "heavy": heavy})

    def _ingest_meta(self, meta):
        phase = meta.get("phase")
        winner = meta.get("winner")
        if phase == self._meta.get("phase") and winner == self._meta.get("winner"):
            return
        self._meta = dict(meta)
        if phase == "over":
            self.events.append({"t": "over", "winner": int(winner if winner is not None
                                                         else 1 - self.you)})

    # ---------- arbitragem (só o host) ----------
    def _near_history(self, side, x, y, rng):
        """A vítima passou perto desse ponto nos últimos segundos?

        É a compensação de lag: o atirador viu um fantasma velho, então o
        tiro é julgado no ponto que ele VIU, não onde a vítima está agora.
        """
        cut = time.time() - C.NET_HIT_WINDOW
        for t, hx, hy in reversed(self._hist[side]):
            if t < cut:
                break          # o histórico é antigo demais (vem do mais novo pro mais velho)
            if (hx - x) ** 2 + (hy - y) ** 2 <= rng * rng:
                return True
        return False

    def _arbitrate_hit(self, side, seq, dmg, heavy, aim=None):
        victim = 1 - side
        now = time.time()
        # o árbitro não carrega previsão pendente do dano que acabou de decidir
        self.pred[victim].pop(seq, None)
        self._resolved[victim].add(seq)
        hpv = dict(self.hp[victim])
        reject = False
        if hpv["lives"] <= 0 or hpv["hp"] <= 0:
            reject = True
        elif hpv["inv"] > now:
            reject = True
        elif self._cd[side] > now:
            reject = True
        else:
            rng = C.NET_HEAVY_RANGE if heavy else C.NET_CHIP_RANGE
            if aim is not None:
                # o tiro foi julgado no ponto que o atirador viu: confere
                # contra o histórico da vítima (ela já pode ter mudado de lugar)
                if not self._near_history(victim, aim[0], aim[1], rng):
                    reject = True
            else:
                me, foe = self._states[side], self._states[victim]
                if not isinstance(me, dict) or not isinstance(foe, dict):
                    reject = True
                else:
                    dist = math.hypot(float(me.get("x", 0)) - float(foe.get("x", 0)),
                                      float(me.get("y", 0)) - float(foe.get("y", 0)))
                    if dist > rng:
                        reject = True
        lost = False
        if reject:
            dmg = 0.0
        else:
            dmg = max(1.0, min(80.0, dmg))
            self._cd[side] = now + (C.NET_HEAVY_CD if heavy else C.CHIP_CD)
            if not heavy:
                self._cd[victim] = now + C.CHIP_CD
            self.hp[victim]["hp"] = float(hpv["hp"]) - dmg
            self.hp[victim]["inv"] = now + (C.INV_HEAVY if heavy else 0.0)
            if self.hp[victim]["hp"] <= 0:
                self.hp[victim]["hp"] = C.HP_MAX
                self.hp[victim]["lives"] = int(hpv["lives"]) - 1
                self.hp[victim]["inv"] = now + 2.0
                lost = True
        self._publish_hp(victim, seq, heavy, dmg, lost)
        if not reject:
            self.events.append({"t": "dmg", "side": victim, "hp": self.hp[victim]["hp"],
                                "lives": self.hp[victim]["lives"], "lost": lost,
                                "heavy": heavy, "dmg": dmg})
        if self.hp[victim]["lives"] <= 0:
            self._publish_meta("over", side)

    def _arbitrate_fell(self, side, seq):
        me = dict(self.hp[side])
        if me["lives"] > 0:
            self.hp[side]["hp"] = C.HP_MAX
            self.hp[side]["lives"] = int(me["lives"]) - 1
            self.hp[side]["inv"] = time.time() + 2.0
        self._publish_hp(side, seq, False, 0.0, me["lives"] > 0)
        if self.hp[side]["lives"] <= 0:
            self._publish_meta("over", 1 - side)

    def _publish_hp(self, side, claim_seq, heavy, dmg, lost):
        hp = self.hp[side]
        seq = self._next_hp_seq(side)
        payload = {"hp": float(hp["hp"]), "lives": int(hp["lives"]),
                   "inv": float(hp["inv"]), "seq": seq,
                   "last_claim": int(claim_seq), "dmg": float(dmg),
                   "heavy": bool(heavy), "lost": bool(lost),
                   "ts": int(time.time() * 1000)}
        self._hp_seq[side] = seq  # o árbitro já sabe: não reingere o próprio texto
        try:
            self.transport.write(f"{self.base}/hp{side}", payload)
        except FbError as e:
            self._last_error = str(e)
            if e.fatal:
                self._alive = False
        if lost:
            self.events.append({"t": "reset", "side": side, "hp": float(hp["hp"]),
                                "lives": int(hp["lives"])})

    def _next_hp_seq(self, side):
        self._hp_write[side] = self._hp_write.get(side, 0) + 1
        return self._hp_write[side]

    def _publish_meta(self, phase, winner):
        try:
            self.transport.write(f"{self.base}/meta", {
                "phase": phase, "winner": int(winner),
                "ts": int(time.time() * 1000)})
        except FbError as e:
            self._last_error = str(e)
        self._meta = {"phase": phase, "winner": int(winner)}
        if phase == "over":
            # o árbitro já sabe: avisa logo, sem esperar o passeio do nó
            self.events.append({"t": "over", "winner": int(winner)})
