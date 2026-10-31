"""Builda (zipa) todos os ports em ports/, vendoring o core antes.

Uso: python tools/build_all.py [--port <id>]
"""
import argparse
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTS = os.path.join(ROOT, "ports")


def vendor(pid):
    src = os.path.join(ROOT, "core")
    dst = os.path.join(PORTS, pid, "core")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def build(pid):
    pdir = os.path.join(PORTS, pid)
    if not os.path.isdir(pdir) or pid.startswith("_"):
        return None
    vendor(pid)
    # nome do zip a partir do port.json se existir
    import json
    name = pid + ".zip"
    pj = os.path.join(pdir, "portmaster", "port.json")
    if os.path.exists(pj):
        try:
            with open(pj, encoding="utf-8") as f:
                name = json.load(f).get("name", name)
        except Exception:
            pass
    out = os.path.join(ROOT, "dist", name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(pdir):
            for fn in files:
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, os.path.dirname(pdir))
                z.write(full, arc)
    print("built", out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=None)
    args = ap.parse_args()
    if args.port:
        build(args.port)
        return
    for pid in sorted(os.listdir(PORTS)):
        if os.path.isdir(os.path.join(PORTS, pid)):
            build(pid)


if __name__ == "__main__":
    main()