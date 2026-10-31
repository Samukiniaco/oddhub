# CaVo — port para dArkOS (default e dArkOS4Clone) via PortMaster

Pasta de staging (separada do codigo do jogo). Estrutura pronta para uso.

## Estrutura
- `CaVo.sh` — script solto (vai para `/roms/ports/`)
- `cavo/` — pasta do jogo (vai para `/roms/ports/cavo/`)
- `portmaster/` — metadados para distribuicao no PortMaster (port.json, gameinfo.xml, screenshot, README)

## Como usar no dispositivo (manual)
1. Copie `CaVo.sh` para `/roms/ports/`.
2. Copie a pasta `cavo/` para `/roms/ports/cavo/`.
3. `chmod +x /roms/ports/CaVo.sh`
4. Instale o runtime `python_3.11` pelo PortMaster (Runtime Manager).
5. Copie os arquivos do jogo para `/roms/ports/cavo/`:
   - `main.py` e a pasta `cavo/` (modulos).
   - (opcional) `texts.json`, `sprites/`.
6. Se pygame-ce nao estiver no runtime, coloque os pacotes em `/roms/ports/cavo/site-packages/`
   (use `fetch_deps.sh` em maquina aarch64).
7. Rode CaVo pelo menu Ports (EmulationStation).

## Distribuicao via PortMaster
Copie a pasta `portmaster/` + `CaVo.sh` + `cavo/` para `ports/cavo/` no repo
do PortMaster e gere o zip com `python3 tools/build_release.py`.

## Observacoes
- Port de dados (rtr=false): usuario fornece os arquivos do jogo.
- Online (nuvem/relay) requer rede e `requests`.
- Controles: gamepad nativo SDL; saida via Select+Start (gptokeyb).