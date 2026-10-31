"""Contrato normalizado de 'serviço' (app) e de 'item' de conteúdo.

Um serviço é um plugin que sabe buscar dados de um app (API oficial ou
scraping) e devolver itens normalizados. A UI do core só conhece `Item`,
nunca o formato original do app.
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol


@dataclass
class Item:
    """Unidade normalizada de conteúdo exibível."""
    id: str
    title: str
    subtitle: str = ""
    image_url: str = ""
    media_url: str = ""
    kind: str = "card"          # card | list | video | audio | text
    meta: dict = field(default_factory=dict)


class Service(Protocol):
    """Contrato que todo app/serviço deve implementar."""

    id: str
    name: str

    def authenticate(self, creds: dict) -> bool:
        """Autentica (se necessário). Retorna True se OK."""
        ...

    def fetch_home(self) -> List[Item]:
        """Conteúdo inicial (feed/home)."""
        ...

    def search(self, query: str) -> List[Item]:
        """Busca por texto."""
        ...

    def open(self, item: Item) -> Any:
        """Abre um item (retorna uma View/dict de tela)."""
        ...


class BaseService:
    """Base com defaults úteis para implementações concretas."""

    id: str = "base"
    name: str = "Base"

    def __init__(self, http=None, cache=None):
        self.http = http
        self.cache = cache

    def authenticate(self, creds: dict) -> bool:
        return True

    def fetch_home(self) -> List[Item]:
        return []

    def search(self, query: str) -> List[Item]:
        return []

    def open(self, item: Item) -> Optional[dict]:
        return {"item": item}