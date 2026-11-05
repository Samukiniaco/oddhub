#!/usr/bin/env python3
"""Script simples para testar o port PortMail."""

import os
import sys

# Adiciona o diretório atual ao caminho
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

print("Testando port PortMail...")
print("Executando self-test (sem UI)...")

# Importa e executa o main com args
from gmail.main import main

# Testa o selftest
result = main(['--selftest'])

if result == 0:
    print("OK Self-test passou!")
    sys.exit(0)
else:
    print("ERRO Self-test falhou!")
    sys.exit(1)
