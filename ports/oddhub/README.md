# OddHub (gerenciador de ports)

Port que lista e abre os apps da coletânea. Compartilha o `core/`.

- `services/`: pacote com os `service.py` dos apps incluídos (copiados via build).
- Rode `python tools/sync_core.py hub` e copie os services desejados para
  `ports/hub/services/` antes de gerar a release.