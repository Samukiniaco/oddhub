"""Copia os arquivos do jogo para a pasta do port (para teste no dispositivo).
Uso (da pasta port/): python sync_game.py
"""
import shutil, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
PORT = os.path.dirname(os.path.abspath(__file__))                   # port/
DST = os.path.join(PORT, "cavo")                                   # gamedir
os.makedirs(DST, exist_ok=True)
for name in ("main.py", "texts.json"):
    p = os.path.join(ROOT, name)
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(DST, name))
src_cavo = os.path.join(ROOT, "cavo")
dst_cavo = os.path.join(DST, "cavo")
if os.path.exists(dst_cavo):
    shutil.rmtree(dst_cavo)
shutil.copytree(src_cavo, dst_cavo)
for name in ("sprites",):
    sp = os.path.join(ROOT, name)
    if os.path.isdir(sp):
        dp = os.path.join(DST, name)
        if os.path.exists(dp):
            shutil.rmtree(dp)
        shutil.copytree(sp, dp)
print("Sincronizado em", DST)