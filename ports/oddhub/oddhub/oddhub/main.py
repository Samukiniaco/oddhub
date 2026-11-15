"""Ponto de entrada do gerenciador OddHub.

    python3 -m oddhub
    python3 -m oddhub --selftest
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_GAME = os.path.dirname(_HERE)
_ROOT = os.path.dirname(os.path.dirname(_GAME))


def _bootstrap() -> None:
    if _GAME not in sys.path:
        sys.path.insert(0, _GAME)
    for candidate in (_GAME, _ROOT):
        if os.path.isdir(os.path.join(candidate, "core")):
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
            return


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="oddhub", description="Gerenciador OddHub")
    parser.add_argument("--fullscreen", action="store_true", help="abre em tela cheia")
    parser.add_argument("--windowed", action="store_true", help="forca janela (testes no PC)")
    parser.add_argument("--width", type=int, default=0, help="largura da janela")
    parser.add_argument("--height", type=int, default=0, help="altura da janela")
    parser.add_argument("--selftest", action="store_true", help="roda os testes rapidos e sai")
    return parser.parse_args(argv)


def _selftest() -> int:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from oddhub import manifest
    from oddhub.app import HubApp

    app = HubApp(window_size=(640, 480), headless=True)
    app.step(1 / 60)
    assert app.ports is not None
    print("selftest ok")
    print(f"  ports na colecao: {len(app.ports)}")
    print(f"  pasta de ports: {manifest.ports_root()}")
    app.shutdown()
    return 0


def _run_gui(args) -> int:
    from oddhub.app import HubApp

    fullscreen = None
    if args.fullscreen:
        fullscreen = True
    elif args.windowed:
        fullscreen = False
    size = (args.width, args.height) if args.width and args.height else None

    app = HubApp(fullscreen=fullscreen, window_size=size)
    try:
        app.run()
    finally:
        try:
            app.shutdown()
        except Exception:
            pass
    return 0


def main(argv=None) -> int:
    _bootstrap()
    try:
        from core.process import set_process_name

        set_process_name("oddhub")
    except Exception:
        pass
    args = _parse_args(argv)
    if args.selftest:
        try:
            return _selftest()
        except Exception:
            traceback.print_exc()
            return 1
    try:
        return _run_gui(args)
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
