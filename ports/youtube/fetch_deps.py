"""Baixa dependencias para o dispositivo (aarch64/cp311)."""
import subprocess, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
REQ = os.path.join(HERE, "requirements.txt")
OUT = os.path.join(HERE, "site-packages")
os.makedirs(OUT, exist_ok=True)
print("Instalando deps de", REQ, "em", OUT)
# Ajuste o index/plataforma conforme o dispositivo alvo.
subprocess.run([sys.executable, "-m", "pip", "install", "-r", REQ,
                "--target", OUT, "--upgrade"], check=False)
print("Pronto. Copie site-packages/ para o dispositivo.")
