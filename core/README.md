# core do OddHub

Base compartilhada por todos os ports da colecao. Nao conhece nenhum app
especifico: sao as partes que se repetem em todo port e que precisam ficar
identicas na tela e no comportamento do controle.

## O que tem aqui

| Modulo | Para que serve |
|---|---|
| `app.py` | `BaseApp`: janela 640x480 logica escalada para a tela real, loop, avisos, clique por toque |
| `theme.py` | `Theme`: paleta e medidas. Cada port copia e troca o que quiser |
| `ui/widgets.py` | Texto, corte, quebra de linha, icones vetoriais, avatar, scrollbar, toast |
| `ui/keyboard.py` | Teclado virtual navegavel pelo controle (setas, mouse, teclado fisico) |
| `ui/avatars.py` | Iniciais e previa de texto |
| `backend.py` | Contrato de backend: fila de eventos, status, `emit`/`poll` |
| `storage.py` | Pasta de dados no XDG, cache, JSON atomico |
| `process.py` | Nome do processo (kill switch do gptokeyb2), dados do aparelho, log |
| `net/http.py` | HTTP sobre `urllib` (sem `requests`, sem dependencia extra) |
| `net/cache.py` | Cache em disco com tempo de vida |
| `media/audio.py` | Efeitos e musica com o mixer do pygame |

## Como um port usa o core

O port importa o core normalmente:

```python
from core.app import BaseApp
from core.ui import widgets
```

Para o port funcionar sozinho no aparelho, o core precisa estar dentro da
pasta do jogo:

```bash
python tools/sync_core.py gmail
```

Esse comando copia `core/` para `ports/gmail/gmail/core/`. A copia nao vai para
o git (esta no `.gitignore`) e entra no zip na hora da build.

## Regras que o core segue

- Nada de joystick: o controle chega pelo gptokeyb2, como tecla.
- Nada de glifo fora do ASCII: a fonte padrao do pygame nao tem setas nem
  simbolos, e eles virariam caixas vazias. Icone e desenhado.
- Nada de `requests` nem de biblioteca extra: o runtime do PortMaster so
  garante a biblioteca padrao.
- Tela sempre em 640x480 logica, escalada para a tela real.
