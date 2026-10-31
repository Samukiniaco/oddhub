"""Cliente HTTP fino sobre requests, com retry e sessão persistente."""
import time

try:
    import requests
except ImportError:  # ambiente de teste sem requests
    requests = None


class HttpClient:
    def __init__(self, timeout=10.0, retries=2, headers=None):
        self.timeout = timeout
        self.retries = retries
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (PortMaster-port) AppleWebKit/537.36"
        }
        self._session = None

    def _sess(self):
        if self._session is None and requests is not None:
            self._session = requests.Session()
            self._session.headers.update(self.headers)
        return self._session

    def request(self, method, url, **kw):
        if requests is None:
            raise RuntimeError("requests não disponível")
        kw.setdefault("timeout", self.timeout)
        last = None
        for _ in range(self.retries + 1):
            try:
                r = self._sess().request(method, url, **kw)
                return r
            except Exception as e:
                last = e
                time.sleep(0.5)
        raise last

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)