"""Baixa e instala dependencias do CaVo para aarch64 (Windows/Linux/macOS).

Cria duas pastas:
  site-packages/  -> pygame-ce + requests (fallback com runtime python_3.11 + wheel)
  deps/           -> so requests (p/ runtime pygame-ce do dispositivo, onde o pygame ja vem embutido)

Uso:
    python fetch_deps.py
"""
import subprocess, sys, os

base = os.path.dirname(os.path.abspath(__file__))
targets = [
    (os.path.join(base, "site-packages"), ["pygame-ce", "requests"]),
    (os.path.join(base, "deps"), ["requests"]),
]

for dst, pkgs in targets:
    os.makedirs(dst, exist_ok=True)
    cmd = [sys.executable, "-m", "pip", "install",
           "--target", dst, "--only-binary=:all:", "--no-cache-dir",
           "--platform", "manylinux_2_17_aarch64",
           "--python-version", "3.11", "--abi", "cp311"] + pkgs
    print("Instalando", pkgs, "em", dst)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("Falhou para", dst, "— verifique conexao/pip.")
        sys.exit(r.returncode)

print("Pronto. Copie site-packages/ e deps/ para /roms/ports/cavo/ no dispositivo.")