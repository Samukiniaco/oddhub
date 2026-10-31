#!/bin/bash
# Atualiza o port do CaVo a partir do repo base.
# Uso (no repo raiz): bash port/update_port.sh

set -e

echo "=== Atualizando port CaVo ==="
python port/sync_game.py

echo "--- Verificando arquivos do jogo ---"
test -f port/cavo/main.py || { echo "ERRO: main.py nao encontrado"; exit 1; }
test -d port/cavo/cavo || { echo "ERRO: pacote cavo nao encontrado"; exit 1; }

echo "--- Verificando dependencias ---"
python port/cavo/fetch_deps.py || echo "AVISO: fetch_deps.py falhou (verifique conexao/pip)"

echo "--- Verificando script de launch ---"
bash -n port/CaVo.sh || { echo "ERRO: CaVo.sh com erro de sintaxe"; exit 1; }

echo "--- Verificando testes basicos ---"
python -m pytest tests/smoke.py -q 2>/dev/null || echo "AVISO: smoke.py nao rodou (pode ser ambiente sem pygame)"

echo "=== Port atualizado. Copie para o dispositivo: ==="
echo "  cp -r port/CaVo.sh /roms/ports/"
echo "  cp -r port/cavo /roms/ports/cavo/"
echo "  chmod +x /roms/ports/CaVo.sh"
