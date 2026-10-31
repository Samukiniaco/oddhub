"""Cache em disco com TTL (para imagens e respostas)."""
import json
import os
import time


class DiskCache:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, key):
        safe = "".join(c if c.isalnum() else "_" for c in str(key))
        return os.path.join(self.root, safe + ".json")

    def get(self, key, ttl=None):
        p = self._path(key)
        if not os.path.exists(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except (OSError, ValueError):
            return None
        if ttl is not None and time.time() - obj.get("_ts", 0) > ttl:
            return None
        return obj.get("value")

    def set(self, key, value):
        p = self._path(key)
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"_ts": time.time(), "value": value}, f)
        except OSError:
            pass

    def remove(self, key):
        p = self._path(key)
        try:
            os.remove(p)
        except OSError:
            pass