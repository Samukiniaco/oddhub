## CaVo (Carvalhinhos Voadores) — port PortMaster (dArkOS / ArkOS)

Port de dados: o pacote nao inclui os arquivos do jogo. Apos instalar o port,
copie os arquivos do jogo para `/roms/ports/cavo/`.

### Arquivos necessarios (copiar para /roms/ports/cavo/)
- `main.py`
- pasta `cavo/` (com todos os modulos .py)
- `deps/` — so `requests` (gerado por `python fetch_deps.py`)
- (opcional) `site-packages/` — pygame-ce + requests (fallback, veja abaixo)
- (opcional) `texts.json` — recriado pelo jogo se faltar
- (opcional) `sprites/` e `sprites/manifest.json` — se usar sprites

### Runtime (obrigatorio para dispositivos com Mali fbdev)
O wheel do pygame-ce do PyPI embute uma SDL2 nova que falha no Mali fbdev
(`Can't window GBM/EGL surfaces on window creation`). Use o runtime
[pygame-ce-runtime](https://github.com/viniciusfs/pygame-ce-runtime):

1. Baixe de https://github.com/viniciusfs/pygame-ce-runtime/releases/tag/v0.3.0:
   - `pygame-ce_2.5.6_python_3.12.8.squashfs` (xz, menor) — tente este primeiro;
   - `pygame-ce_2.5.6_python_3.12.8_gzip.squashfs` — se o montar falhar com
     `wrong fs type / bad superblock` (kernel sem xz).
2. Copie o arquivo para `/opt/system/Tools/PortMaster/libs/` (ou para
   `/roms/ports/cavo/`).
3. O `CaVo.sh` monta automaticamente e usa esse python+pygame.

Se o runtime nao estiver presente, o script cai para `python_3.11` do
PortMaster + `site-packages/` (so funciona em dispositivos onde a SDL2 do
wheel e compativel).

### Gerar deps no PC (Windows/Linux)
```
python fetch_deps.py
```
Cria `site-packages/` (pygame-ce+requests, cp311 aarch64) e `deps/`
(só requests). Copie as duas pastas para `/roms/ports/cavo/`.

### Controles
- Gamepad nativo (SDL). D-Pad/sticks conforme configurado no menu Controles.
- ESC / Select+Start: sair (via gptokeyb).

### Notas
- Online (nuvem/relay) depende de rede e de `requests`.
- Ajuste de resolucao via menu do jogo (F11 alterna video).
- Log completo em `/roms/ports/cavo/log.txt` apos cada execucao.
