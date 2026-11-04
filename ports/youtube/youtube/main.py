"""Entry point do port PortTube."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# core vendored esperado em ./core ; fallback para raiz do repo
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.isdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "core")):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
elif os.path.isdir(os.path.join(root, "core")):
    sys.path.insert(0, root)

from core.platform.storage import game_dir


def main():
    print("Port PortTube iniciado. Implemente a UI sobre core.")


if __name__ == "__main__":
    main()
