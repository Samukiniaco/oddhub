# PORTS.md - acompanhamento da colecao

Este arquivo e gerado por `python tools/tracker.py --write`.
O registro que manda e `ports/registry.json`.

Legenda de status: planejado (esta no registro, sem codigo) | em andamento (codigo comecando) | em teste (rodando, falta testar no aparelho) | funcional (rodando e testado) | pausado

## Nucleo e gerenciador

| Item | Status | Notas |
|------|--------|-------|
| core (base compartilhada) | em uso | base compartilhada: janela 640x480 escalada, widgets, teclado virtual, contrato de backend, storage, http sem dependencia extra |
| oddhub (gerenciador) | em teste | gerenciador da colecao: lista os ports instalados e abre o escolhido |

## Apps

| Id | Port | Tipo | Abordagem | Status | Prioridade |
|----|------|------|-----------|--------|------------|
| gmail | PortMail | mail | imap/smtp | em teste | 4 |
| pinterest | Pinterest | image | api | planejado | 3 |
| crunchyroll | Crunchyroll | streaming | api | planejado | 2 |
| youtube | YouTube | video | yt-dlp | planejado | 1 |

## Como mexer

- `python tools/new_port.py <id> "Nome"` cria um port novo a partir do template
- `python tools/sync_core.py <id>` copia o core para dentro do port
- `python tools/build_all.py` monta os zips de teste
- `python tools/port_manager.py` abre o gerenciador grafico do registro
