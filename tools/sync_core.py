"""Vende o core/ para dentro de um port (para distribuicao).

Uso: python tools/sync_core.py <port_id>
Copia core/ para ports/<port_id>/core/.
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 2:
        print("uso: sync_core.py <port_id>")
        sys.exit(1)
    pid = sys.argv[1]
    src = os.path.join(ROOT, "core")
    dst = os.path.join(ROOT, "ports", pid, "core")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print("core vendored em", dst)


if __name__ == "__main__":
    main()