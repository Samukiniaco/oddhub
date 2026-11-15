# Arquitetura do OddHub

## Ideia

Um port = uma pasta em `ports/<id>/`, com um release proprio. O que se repete
entre eles vive no `core/`. Assim o comportamento do controle, o tamanho da
tela e as regras de empacotamento sao iguais em todos, e so a logica do app
muda.

## Layout de um port (layout de PR do PortMaster)

```
ports/<id>/
  port.json            # schema v4 do PortMaster
  gameinfo.xml         # metadados para a interface do CFW
  README.md            # notas + controles
  testing_thread.txt   # texto do thread de teste
  screenshot.png       # 640x480, ate 100 KB
  <Nome>.sh            # launcher (nome do titulo, com espaco)
  <id>/                # pasta do jogo (nome do id, sem espaco)
    main.py            # ponto de entrada
    <id>.ini           # mapa de controles do gptokeyb2
    fetch_deps.py      # gera site-packages/ no PC
    licenses/
    core/              # copia do core (vendored, fora do git)
    <pacote>/          # codigo do port
```

O `.sh` fica do lado da pasta do jogo, nunca dentro dela. O `core/` e copiado
para dentro da pasta do jogo por `tools/sync_core.py` e entra no zip.

## O core

| Modulo | Responsabilidade |
|---|---|
| `app.py` | `BaseApp`: janela 640x480 logica escalada para a tela real, loop, avisos, clique, painel de modal |
| `theme.py` | `Theme`: paleta e medidas, com `copy()` para o port ajustar |
| `ui/widgets.py` | texto, corte, quebra de linha, icones vetoriais, avatar, scrollbar, toast |
| `ui/keyboard.py` | teclado virtual navegavel por setas, mouse e teclado fisico |
| `ui/avatars.py` | iniciais e previa de texto |
| `backend.py` | `Backend`: fila de eventos, status, `emit`/`poll` |
| `storage.py` | pasta de dados no XDG, cache, JSON atomico |
| `process.py` | nome do processo (kill switch), dados do aparelho, log |
| `net/http.py` | HTTP sobre `urllib` |
| `net/cache.py` | cache em disco com TTL |
| `media/audio.py` | efeitos e musica com o mixer do pygame |

## Fluxo de um port

1. **Launcher** (`<Nome>.sh`): acha o `controlfolder`, carrega `control.txt` e
   o `mod_${CFW_NAME}.txt`, monta o runtime (pygame-ce em squashfs, ou
   `python_3.11`), faz `bind_directories` dos dados para `conf/<id>/`, sobe o
   gptokeyb2 com o `.ini` do port e roda `python3 -m <pacote>`.
2. **App**: herda de `BaseApp`, define o tema, o backend e as telas. O loop e
   do core: eventos, `update`, `draw`, `present`.
3. **Backend**: roda em thread quando fala com rede, avisa a UI por eventos.
   A UI nunca bloqueia esperando o servidor.

## Build

`tools/build_all.py`:

1. gera o manifesto da colecao para o gerenciador (`ports.json`);
2. roda `sync_core.py` em cada port;
3. monta o zip no layout instalado (script na raiz, pasta do jogo com os
   metadados dentro);
4. escreve em `dist/<nome>.zip`.

## Gerenciador (oddhub)

Le o `ports.json` que veio no pacote e procura os ports instalados no cartao
(a pasta de ports varia por CFW). Mostra o que existe, o que falta e abre o
escolhido pelo `.sh` dele.

## Registro e acompanhamento

- `ports/registry.json` e a fonte de verdade (maquina).
- `PORTS.md` e gerado por `tools/tracker.py --write`.
- `tools/port_manager.py` edita o registro e as notas de cada port
  (`ports/<id>/NOTES.md`).

## Regras de portabilidade

- Entrada so por tecla: o gptokeyb2 traduz o controle. Nada de
  `SDL_JoystickOpen` no app.
- Desenho em 640x480 logico, escala suave para a tela real.
- Campos de texto leem `pygame.TEXTINPUT`, para teclado fisico ou OSK do
  sistema funcionar, e ha um teclado virtual proprio como garantia.
- Sem `requests` e sem dependencia extra: stdlib + pygame.
- Sem glifo fora do ASCII: fonte padrao do pygame nao tem seta nem simbolo.

## Riscos por app

- **DRM**: servicos com Widevine/PlayReady (Netflix, Crunchyroll) nao deixam
  reproduzir por conta propria. Nesses casos o port faz metadata e link.
- **API/ToS**: cada servico tem sua regra. O port usa o caminho oficial
  quando existe, e o usuario fornece a propria credencial.
- **Marca**: o port nao copia nome, logo, cor ou layout de servico de
  terceiro. Se o id no registro coincide com o nome de um servico, e so
  referencia interna; o nome exibido e do port.