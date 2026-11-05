# Pinterest — Port para PortMaster (OddHub)

## Visão geral

Feed de pins do Pinterest em grade masonry para handhelds/PortMaster, com UI em
pygame. Funciona 100% offline em modo demo e tem backend opcional para a API
real v5 do Pinterest.

## Funcionalidades

### Modo Demo (offline, padrão)
- 26 pins de exemplo em 5 boards (receitas, arte, DIY, moda, tech)
- Miniaturas procedurais determinísticas (sem internet)
- Busca, boards, salvos — tudo funcional sem rede

### Modo API real (opcional)
- API v5 do Pinterest com token Bearer (`PINTEREST_TOKEN`)
- Baixa boards e pins da sua conta
- Cache de imagens em disco

## Como usar

```bash
cd ports/pinterest

# self-test (sem UI)
python pinterest/main.py --selftest

# interface (demo)
python pinterest/main.py

# interface (API real)
PINTEREST_TOKEN=xxx python pinterest/main.py --backend api

# PortMaster
./Pinterest.sh
```

## Navegação

- **Setas/dpad**: mover seleção na grade · **A/Enter**: abrir pin · **B/Esc**: voltar
- **X**: buscar · **Y**: boards · **Start/Select**: configurações
- **Mouse**: clique nos pins e botões · scroll navega
- No pin: **A/Espaço** salva/desalva

## Estrutura

```
ports/pinterest/
├── Pinterest.sh            # launcher PortMaster
├── pinterest/              # pacote do app
│   ├── main.py             # entry point (--selftest, --backend, --fullscreen)
│   ├── config.py           # tema + caminhos
│   ├── models.py           # Pin, Board, eventos
│   ├── store.py            # SQLite (boards, pins, meta)
│   ├── backend/
│   │   ├── base.py         # contrato de backend
│   │   ├── demo.py         # dados de exemplo offline
│   │   └── api_backend.py  # API v5 + cache de imagens
│   └── ui/
│       ├── app.py          # feed masonry, pin, boards, modais
│       ├── widgets.py      # fontes, wrap, miniaturas procedurais
│       └── keyboard.py     # teclado virtual (gamepad/setas/mouse)
├── portmaster/             # port.json + gameinfo.xml
├── requirements.txt
├── fetch_deps.py
└── NOTES.md
```

## Dados

- **Windows**: `%APPDATA%\OddHub\Pinterest\`
- **Linux**: `~/.local/share/oddhub/pinterest/`
- **PortMaster**: `conf/data/` no diretório do port

## Limites

- Sem login social no dispositivo (API real usa token colado)
- Sem upload/publicação de pins (somente leitura + salvos locais)
- Repins/comentários não implementados
