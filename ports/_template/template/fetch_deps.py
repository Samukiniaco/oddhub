"""Gera as dependencias do port para aarch64 (CPython 3.11).

Cria a pasta site-packages/ com pygame-ce, para o caso de o dispositivo nao
ter o runtime pygame-ce instalado.

Uso:
    python fetch_deps.py

Depois copie a pasta site-packages/ para a pasta do port no dispositivo.
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(BASE, "site-packages")

os.makedirs(TARGET, exist_ok=True)
cmd = [
    sys.executable,
    "-m",
    "pip",
    "install",
    "--target",
    TARGET,
    "--only-binary=:all:",
    "--no-cache-dir",
    "--platform",
    "manylinux_2_17_aarch64",
    "--python-version",
    "3.11",
    "--abi",
    "cp311",
    "pygame-ce",
]
print("Instalando pygame-ce em", TARGET)
result = subprocess.run(cmd)
if result.returncode != 0:
    print("Falhou. Verifique a conexao e o pip.")
    sys.exit(result.returncode)
print("Pronto. Copie site-packages/ para a pasta do port no dispositivo.")
