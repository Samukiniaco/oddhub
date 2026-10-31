"""Registro simples de serviços/plugins disponíveis."""
from typing import Dict, Type

from .base import Service


class Registry:
    def __init__(self):
        self._services: Dict[str, Type[Service]] = {}

    def register(self, service_cls: Type[Service]) -> Type[Service]:
        self._services[service_cls.id] = service_cls
        return service_cls

    def get(self, sid: str):
        cls = self._services.get(sid)
        return cls() if cls else None

    def all(self):
        return list(self._services.values())

    def ids(self):
        return list(self._services.keys())


# instância global conveniente
registry = Registry()


def service(id_: str):
    """Decorator para registrar um serviço."""
    def deco(cls):
        cls.id = getattr(cls, "id", id_)
        registry.register(cls)
        return cls
    return deco