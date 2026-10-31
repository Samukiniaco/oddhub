"""CaVo — Fase 1 do online: índice de salas no Firebase RTDB (REST puro).

Sem dependência além de `requests`, sem thread (o jogo chama heartbeat
no loop). Autenticação futura pluga via `set_auth_token()` (?auth=).
Fluxo: criar -> listar/código -> pedir entrada (host aprova) -> heartbeat.
Faxina de sala fantasma: qualquer cliente apaga a velha (ver rules).
Bookmarks (tags locais): {"sexta": "K7Q2M9"} p/ entrar direto pelo apelido.
"""
import hashlib
import json
import os
import random
import time

from . import fbauth
from .texts import T

DB_URL = "https://caravoado-default-rtdb.firebaseio.com"
TIMEOUT = 10
STALE_MIN = 10
VERSION = 1

_auth_token = None
_db_url = DB_URL
_bookmarks_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "bookmarks.json")
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sem I/L/O/0/1 (confusos)


class NetError(Exception):
    pass


def set_db_url(url):
    global _db_url
    _db_url = url.rstrip("/")


def set_auth_token(token):
    """Token manual (custom). Vira ?auth= em tudo."""
    global _auth_token
    _auth_token = token


_auth_enabled = True
_auth_cooldown_until = 0.0


def set_auth_enabled(on):
    global _auth_enabled
    _auth_enabled = bool(on)


def ensure_auth():
    """Garante login anônimo e re-sincroniza o token (best-effort)."""
    global _auth_token, _auth_cooldown_until
    if not _auth_enabled:
        return _auth_token
    if time.time() < _auth_cooldown_until:
        return _auth_token
    try:
        _auth_token = fbauth.token()  # time-check barato; renova sozinho
    except Exception:
        _auth_cooldown_until = time.time() + 60.0
    return _auth_token


def auth_status():
    if _auth_token and fbauth.uid():
        return f"login ok ({fbauth.uid()[:6]}…)"
    return "modo público"


def set_bookmarks_path(path):
    global _bookmarks_path
    _bookmarks_path = path


def gen_code(n=6):
    return "".join(random.choice(CODE_ALPHABET) for _ in range(n))


def hash_pw(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def now_ms():
    return int(time.time() * 1000)


def _url(path):
    u = f"{_db_url}/{path}.json"
    if _auth_token:
        u += f"?auth={_auth_token}"
    return u


def fb_url(path, params=None):
    """URL completa (token válido no ?auth=) para o transporte da partida.

    Garante o login antes de montar a URL: o token expira de hora em hora e
    a partida na nuvem fica horas em pé.
    """
    ensure_auth()
    u = _url(path)
    if params:
        u += ("&" if "?" in u else "?") + params
    return u


def _req(method, path, data=None):
    import requests  # lazy: não existe no browser (online some no web)
    ensure_auth()
    try:
        r = requests.request(method, _url(path), json=data, timeout=TIMEOUT)
    except Exception as e:
        raise NetError(T("net.neterr").format(e=e))
    if r.status_code in (200, 204):
        if method == "GET":
            try:
                return r.json()
            except ValueError:
                raise NetError(T("net.noresp"))
        return True
    if r.status_code in (401, 403):
        raise NetError(T("net.denied"))
    raise NetError(T("net.http").format(code=r.status_code))


def fb_get(path):
    return _req("GET", path)


def fb_put(path, data):
    return _req("PUT", path, data)


def fb_patch(path, data):
    return _req("PATCH", path, data)


def fb_delete(path):
    return _req("DELETE", path)


# ---------- salas ----------
def room_payload(name, password, tag, host_name):
    return {
        "name": name[:30],
        "tag": (tag or "")[:20],
        "hasPassword": bool(password),
        "passHash": hash_pw(password) if password else "",
        "ownerUid": fbauth.uid() or "",  # dono pode apagar; "" = sala antiga
        "status": "open",
        "settings": {"locked": True},  # configs custom: em breve
        "host": {"name": host_name[:16], "seen": now_ms()},
        "version": VERSION,
        "updatedAt": now_ms(),
    }


def create_room(name, host_name, password="", tag=""):
    """Cria e retorna o código (tenta 3x em colisão rara)."""
    ensure_auth()  # garante uid de dono antes de criar
    for _ in range(3):
        code = gen_code()
        if fb_get(f"rooms/{code}") is None:
            fb_put(f"rooms/{code}", room_payload(name, password, tag, host_name))
            return code
    raise NetError(T("net.collision"))


def list_rooms():
    """[(code, sala)] das abertas/jogando, recentes primeiro."""
    all_rooms = fb_get("rooms") or {}
    rooms = [(c, r) for c, r in all_rooms.items()
             if isinstance(r, dict) and r.get("status") in ("open", "playing")]
    rooms.sort(key=lambda kv: kv[1].get("updatedAt", 0), reverse=True)
    return rooms


def get_room(code):
    room = fb_get(f"rooms/{code.upper()}")
    return room if isinstance(room, dict) else None


def request_join(code, name, password=""):
    """Pede entrada; o host aprova. Erro se senha errada."""
    code = code.upper()
    room = get_room(code)
    if not room:
        raise NetError(T("net.no_room"))
    if room.get("status") == "closed":
        raise NetError(T("net.closed"))
    if room.get("hasPassword") and hash_pw(password) != room.get("passHash"):
        raise NetError(T("net.bad_pw"))
    if room.get("guest"):
        raise NetError(T("net.full"))
    fb_put(f"rooms/{code}/joinReq",
           {"name": name[:16], "key": hash_pw(password) if password else "", "seen": now_ms()})
    fb_patch(f"rooms/{code}", {"updatedAt": now_ms()})
    return room


def host_poll(code):
    """Host vê quem quer entrar (joinReq) + se o guest segue vivo."""
    return get_room(code)


def accept_join(code, guest_name):
    fb_patch(f"rooms/{code}", {"guest": {"name": guest_name[:16], "seen": now_ms()},
                               "joinReq": None, "status": "playing", "updatedAt": now_ms()})


def reject_join(code):
    fb_patch(f"rooms/{code}", {"joinReq": None, "updatedAt": now_ms()})


def heartbeat(code, role, name):
    """Chame a cada ~5s no loop: diz 'tô vivo' e devolve a sala."""
    code = code.upper()
    fb_patch(f"rooms/{code}/{role}", {"name": name[:16], "seen": now_ms()})
    fb_patch(f"rooms/{code}", {"updatedAt": now_ms()})
    return get_room(code)


def leave_room(code, role):
    if role == "host":
        close_room(code)
    else:
        fb_patch(f"rooms/{code}", {"guest": None, "status": "open", "updatedAt": now_ms()})


def close_room(code):
    fb_delete(f"rooms/{code.upper()}")


def is_stale(room, now=None):
    now = now if now is not None else now_ms()
    try:
        return (now - int(room.get("updatedAt", 0))) > STALE_MIN * 60 * 1000
    except (TypeError, ValueError):
        return True


def cleanup_stale():
    """Apaga salas fantasmas. Retorna os códigos removidos."""
    all_rooms = fb_get("rooms") or {}
    gone = []
    for code, room in list(all_rooms.items()):
        if isinstance(room, dict) and is_stale(room):
            try:
                fb_delete(f"rooms/{code}")
                gone.append(code)
            except NetError:
                pass
    return gone


# ---------- bookmarks: tag local -> código (entra direto mesmo se o código mudar) ----------
def load_bookmarks():
    try:
        with open(_bookmarks_path, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_bookmarks(marks):
    with open(_bookmarks_path, "w", encoding="utf-8") as f:
        json.dump(marks, f, indent=2)


def tag_room(tag, code):
    marks = load_bookmarks()
    marks[tag] = code.upper()
    save_bookmarks(marks)


def resolve_tag(tag_or_code):
    """Apelido salvo vence; senão, trata como código direto."""
    marks = load_bookmarks()
    if tag_or_code in marks:
        return marks[tag_or_code]
    return tag_or_code.upper()
