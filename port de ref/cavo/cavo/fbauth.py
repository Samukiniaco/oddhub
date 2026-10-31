"""CaVo — Firebase Auth anônima via REST (sem SDK, só stdlib+requests).

Login invisível por aparelho: ninguém digita nada. O token dura 1h e renova
sozinho. A key abaixo é pública por design (vai no código de todo site);
a segurança vem das regras do banco, nunca dela.
"""
import time

FIREBASE_API_KEY = "AIzaSyDtsf4LIelorLZke-AfRDxXUK2QdYNPM7g"
_SIGNUP = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
_REFRESH = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"


class AuthError(Exception):
    pass


_state = {"id_token": None, "refresh_token": None, "exp": 0.0, "uid": None}


def _post(url, payload, timeout=10):
    import requests  # lazy: não existe no browser (online some no web)
    r = requests.request("POST", url, json=payload, timeout=timeout)
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", r.status_code)
        except ValueError:
            msg = r.status_code
        raise AuthError(f"auth recusada: {msg} (liberou 'Anônimo' no console?)")
    return r.json()


def sign_in():
    d = _post(_SIGNUP, {"returnSecureToken": True})
    _state.update(id_token=d["idToken"], refresh_token=d["refreshToken"],
                  exp=time.time() + int(d.get("expiresIn", "3600")) - 60,
                  uid=d.get("localId"))
    return _state["id_token"]


def _refresh():
    d = _post(_REFRESH, {"grant_type": "refresh_token",
                         "refresh_token": _state["refresh_token"]})
    _state.update(id_token=d["id_token"],
                  refresh_token=d.get("refresh_token", _state["refresh_token"]),
                  exp=time.time() + int(d.get("expires_in", 3600)) - 60)
    return _state["id_token"]


def token():
    """Token válido (renova ou loga sozinho). Levanta AuthError se falhar."""
    if _state["id_token"] and time.time() < _state["exp"]:
        return _state["id_token"]
    if _state["refresh_token"]:
        try:
            return _refresh()
        except AuthError:
            pass
    return sign_in()


def uid():
    return _state["uid"]


def reset():
    _state.update(id_token=None, refresh_token=None, exp=0.0, uid=None)
