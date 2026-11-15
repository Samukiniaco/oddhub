# OddHub - colecao de ports para PortMaster

Colecao modular de ports para PortMaster. Cada port e uma pasta em `ports/`, e
todos compartilham o mesmo `core/`: janela, widgets, teclado virtual, contrato
de backend, armazenamento e rede.

Repositorio: https://github.com/Samukiniaco/oddhub

## Estrutura

```
core/                 # base compartilhada (vendored em cada port na build)
ports/
  registry.json       # registro da colecao (maquina)
  _template/          # modelo de port, usado por tools/new_port.py
  oddhub/             # gerenciador: lista e abre os ports instalados
  gmail/              # PortMail: cliente de email IMAP/SMTP
tools/                # sync_core, new_port, build_all, tracker, port_manager, note
docs/architecture.md  # como as pecas se encaixam
PORTS.md              # gerado a partir do registry.json
```

`port de ref/` nao entra no git: e referencia tecnica local.

## O que tem pronto

| Port | O que e | Estado |
|---|---|---|
| `oddhub` | gerenciador da colecao | em teste |
| `gmail` (PortMail) | cliente de email IMAP/SMTP | em teste |

## PortMail

Cliente de email independente, com dois modos:

- **demo**: mensagens de exemplo, funciona sem conta e sem internet.
- **conta**: le e envia pela sua conta IMAP/SMTP (Gmail, Outlook, qualquer
  provedor que fale o protocolo). A senha fica no cartao SD, no arquivo de
  dados do port.

A interface e desenhada em 640x480 e escalada para a tela real, o controle
chega pelo gptokeyb2 e o teclado virtual (L2) cobre os campos de texto.

## Desenvolvimento

Requisitos no PC: Python 3.11+ e pygame-ce (`pip install pygame-ce`).

```bash
# criar um port novo a partir do template
python tools/new_port.py pinterest "Pinterest" --genre other

# copiar o core para dentro do port (necessario antes de rodar/buildar)
python tools/sync_core.py pinterest

# rodar o port no PC
python ports/pinterest/pinterest/main.py

# teste sem abrir tela
python ports/gmail/gmail/portmail/main.py --selftest

# montar o zip de teste (layout que o PortMaster instala)
python tools/build_all.py
python tools/build_all.py --port gmail

# acompanhamento
python tools/tracker.py
python tools/tracker.py --write      # gera o PORTS.md

# editor do registro (Tkinter)
python tools/port_manager.py
```

## Regras que valem para todo port

- Nada de joystick direto: o controle chega pelo gptokeyb2, como tecla. O app
  nao abre a API de joystick do SDL (duplicaria a entrada).
- Nada de glifo fora do ASCII nas telas: a fonte padrao do pygame nao tem
  setas nem simbolos e eles viram caixas vazias. Icone e desenhado.
- Nada de `requests` nem de biblioteca extra: o runtime do PortMaster garante
  a biblioteca padrao do Python. IMAP, SMTP e HTTP saem da stdlib.
- Tela sempre em 640x480 logica, escalada para a resolucao real.
- Nada de `SDL_VIDEODRIVER`, `SDL_AUDIODRIVER`, `HOME=` ou `LD_PRELOAD` no
  launcher: isso e do CFW, nao do port.

## Dependencias no aparelho

Os ports usam o runtime `python_3.11` do PortMaster e precisam de pygame. Duas
formas de resolver:

1. Copiar o runtime `pygame-ce_*.squashfs` para
   `/opt/system/Tools/PortMaster/libs/`. O launcher monta e usa.
2. Gerar o wheel no PC com `python fetch_deps.py` (dentro da pasta do port) e
   copiar a `site-packages/` para a pasta do port no cartao.

## Licenca

MIT. Veja `LICENSE` em cada port.