# Notas — Pinterest

## Estado atual

✅ Port funcional (demo + API real), testado com selftest e smoke test de UI.

## Arquitetura

- `backend/demo.py` — 26 pins / 5 boards seedados, miniaturas procedurais
- `backend/api_backend.py` — Pinterest API v5 (Bearer), download de imagens com cache
- `ui/app.py` — feed masonry (2–5 colunas), detalhe do pin, lista de boards
- `store.py` — SQLite: boards, pins, meta (token, backend)

## Decisões

- Pinterest não tem "login fácil" em dispositivo: API usa token manual
  (PINTEREST_TOKEN ou modal Configurações > Token API).
- Upload não é suportado (PortMaster é leitura/consumo).
- Miniaturas demo são procedurais (nada de assets binários no repo).

## Melhorias futuras

### Prioridade alta
- [ ] Pinch/zoom na imagem do pin
- [ ] Abrir link do pin (via navegador do dispositivo, se houver)
- [ ] Filtrar por tag

### Prioridade média
- [ ] Seção "Semelhantes" ao pin aberto
- [ ] Ordenar feed (recentes / mais salvos)
- [ ] Suporte a múltiplas contas/token

### Prioridade baixa
- [ ] Modo tela dividida com legenda
- [ ] Exportar pins salvos
