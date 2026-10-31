#!/bin/bash
# Instala dependencias do CaVo para aarch64 (rode em maquina aarch64).
set -e
cd "$(dirname "$0")"
for pair in "site-packages pygame-ce requests" "deps requests"; do
  set -- $pair
  DST="$1"; shift
  mkdir -p "$DST"
  python3 -m pip install --target "$DST" --only-binary=:all: --no-cache-dir \
    --platform manylinux_2_17_aarch64 --python-version 3.11 --abi cp311 "$@"
  echo "Instalado em $DST"
done
echo "Pronto. Copie site-packages/ e deps/ para o dispositivo."