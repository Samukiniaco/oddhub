"""CaVo — sessão online do cliente (relay WebSocket): socket em thread +
interpolação do remoto.

Relógio: sem sincronizar com o servidor; interpola na linha do tempo de
CHEGADA (render = último snap − atraso adaptativo). Sem rollback: você
simula 60fps, o oponente é fantasma interpolado, dano só via eventos do
relay. O mesmo netcode (cavo/netcode.py) serve a nuvem (Firebase).
"""
import collections
import json
import socket
import threading
import time
import urllib.parse

from . import ws
from .netcode import Ghost

RENDER_DELAY = 0.12
INPUT_HZ = 20


class OnlineError(Exception):
    pass


def parse_relay(url):
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("ws", "wss"):
        raise OnlineError("URL do relay tem que começar com ws://")
    if u.scheme == "wss":
        raise OnlineError("use ws:// (o Tunnel termina o TLS e entrega local)")
    return u.hostname or "localhost", u.port or 80


def check_relay(url, timeout=2.0):
    """Semáforo rápido: (ok, ms). Só abre TCP, sem handshake."""
    import time
    try:
        host, port = parse_relay(url)
    except OnlineError as e:
        return False, 0.0, str(e)
    t0 = time.time()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True, (time.time() - t0) * 1000.0, ""
    except OSError as e:
        return False, 0.0, str(e)


def _shortest(a, b):
    return (b - a + 180.0) % 360.0 - 180.0


class OnlineSession:
    def __init__(self, url, room, side, name):
        try:
            host, port = parse_relay(url)
        except OnlineError:
            raise
        try:
            self.sock = socket.create_connection((host, port), timeout=8)
            self.sock.settimeout(60.0)
            ws.client_handshake(self.sock, host, urllib.parse.urlparse(url).path or "/")
        except (OSError, ws.WSError) as e:
            hint = " — rode: python relay_server.py" if host in ("localhost", "127.0.0.1") else ""
            raise OnlineError(f"relay fora do ar? ({e}){hint}")
        self.lock = threading.Lock()
        self.snaps = collections.deque(maxlen=16)  # (chegada, [p0, p1])
        self.ghost = Ghost(base_delay=RENDER_DELAY)
        self.events = collections.deque(maxlen=32)
        self.rtt = 0.0
        self._ping_at = 0.0
        self._alive = True
        self._send({"t": "create", "room": room})
        ok = self._expect({"ok", "error"}, timeout=8)
        if ok.get("t") == "error":
            raise OnlineError(ok.get("msg", "relay recusou"))
        self._send({"t": "hello", "room": room, "side": side, "name": name})
        hello = self._expect({"welcome", "error"}, timeout=8)
        if hello.get("t") == "error":
            raise OnlineError(hello.get("msg", "relay recusou"))
        self.you = int(hello.get("you", 0))
        self.room = room
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def _send(self, obj):
        raw = json.dumps(obj)
        with self.lock:
            ws.send_msg(self.sock, raw, mask=True)

    def _expect(self, kinds, timeout=8):
        self.sock.settimeout(timeout)
        try:
            while True:
                raw = ws.recv_msg(self.sock)
                if raw is None:
                    raise OnlineError("relay fechou")
                m = json.loads(raw)
                if m.get("t") in kinds:
                    return m
        except (ws.WSError, ValueError) as e:
            raise OnlineError(str(e))
        finally:
            self.sock.settimeout(60.0)

    def _recv_loop(self):
        try:
            while self._alive:
                raw = ws.recv_msg(self.sock)
                if raw is None:
                    break
                try:
                    m = json.loads(raw)
                except ValueError:
                    continue
                t = m.get("t")
                if t == "snap":
                    arr = time.time()
                    ps = m.get("p", [])
                    self.snaps.append((arr, ps))
                    try:
                        self.ghost.push(ps[1 - self.you], arr)
                    except (IndexError, TypeError):
                        pass
                elif t == "pong":
                    if self._ping_at:
                        self.rtt = time.time() - self._ping_at
                elif t in ("dmg", "reset", "over", "error"):
                    self.events.append(m)
        except (OSError, ws.WSError):
            pass
        self._alive = False

    # ---------- envio (chamado no loop do jogo) ----------
    def send_inputs(self, seq, pl):
        self._send({"t": "in", "seq": seq, "x": pl.p.x, "y": pl.p.y,
                    "vx": pl.v.x, "vy": pl.v.y, "a": pl.angle,
                    "jet": bool(pl.jetting), "stam": pl.stamina})

    def send_hit(self, dmg, heavy, x=None, y=None):
        # x/y = onde o tiro acertou (o relay julga pela distância entre as
        # posições que ele recebeu; a nuvem usa o ponto + histórico)
        self._send({"t": "hit", "dmg": dmg, "heavy": bool(heavy),
                    "x": x, "y": y})

    def send_fell(self):
        self._send({"t": "fell"})

    def ping(self):
        self._ping_at = time.time()
        try:
            self._send({"t": "ping", "c": self._ping_at})
        except (OSError, ws.WSError):
            pass

    def poll_events(self):
        out = list(self.events)
        self.events.clear()
        return out

    # ---------- fantasma interpolado ----------
    def interp_foe(self):
        """Estado (x,y,vx,vy,a,jet,hp,lives,stam,ok,fresh) do oponente, ou None."""
        if not self.snaps:
            return None
        foe = 1 - self.you
        g = self.ghost.sample()
        if not g:
            return None
        try:
            b = self.snaps[-1][1][foe]
        except (IndexError, TypeError):
            b = {}
        out = dict(g)
        out["hp"] = b.get("hp", 100)
        out["lives"] = b.get("lives", 3)
        out["stam"] = b.get("stam", 100)
        out["ok"] = bool(b.get("ok"))
        out["fresh"] = (time.time() - self.snaps[-1][0]) < 1.5
        return out

    @property
    def alive(self):
        return self._alive

    def close(self):
        self._alive = False
        try:
            ws.send_close(self.sock, mask=True)
            self.sock.close()
        except OSError:
            pass
