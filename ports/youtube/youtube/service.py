"""Serviço do app PortTube."""
from core.scrape.base import BaseService, Item


class Service(BaseService):
    id = "youtube"
    name = "PortTube"

    def fetch_home(self):
        # TODO: implementar busca de dados (API oficial ou scraping)
        return [Item(id="1", title="Exemplo", subtitle="placeholder")]

    def search(self, query):
        return []

    def open(self, item):
        return {"item": item}
