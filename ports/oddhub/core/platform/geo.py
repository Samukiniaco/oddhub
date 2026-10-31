"""Geolocalização abstraída (IP/GPS). Implementação mínima por enquanto."""
import json


def by_ip():
    """Retorna (lat, lon, city) via serviço de IP, ou None se falhar."""
    try:
        import urllib.request
        with urllib.request.urlopen("https://ipapi.co/json/", timeout=5) as r:
            d = json.loads(r.read().decode())
        return float(d.get("latitude")), float(d.get("longitude")), d.get("city")
    except Exception:
        return None