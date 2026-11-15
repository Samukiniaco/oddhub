"""Ponto de entrada do port {{TITLE}}.

    python3 -m {{PACKAGE}}
    python3 -m {{PACKAGE}} --selftest
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback

# O core vem junto com o port (pasta core/ dentro do jogo). No repositorio de
# desenvolvimento ele esta na raiz do projeto.
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
    parser = argparse.ArgumentParser(prog="{{ID}}", description="{{TITLE}} para PortMaster")
    parser.add_argument("--fullscreen", action="store_true", help="abre em tela cheia")
    parser.add_argument("--windowed", action="store_true", help="forca janela (testes no PC)")
    parser.add_argument("--width", type=int, default=0, help="largura da janela")
    parser.add_argument("--height", type=int, default=0, help="altura da janela")
    parser.add_argument("--data-dir", default="", help="pasta de dados alternativa")
    parser.add_argument("--selftest", action="store_true", help="roda os testes rapidos e sai")
    return parser.parse_args(argv)


def _selftest() -> int:
    """Confere que o core esta acessivel e que o app abre e fecha."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from {{PACKAGE}}.app import {{CLASS}}

    app = {{CLASS}}(window_size=(640, 480), headless=True)
    app.step(1 / 60)
    app.shutdown()
    print("selftest ok")
    return 0


def _run_gui(args) -> int:
    from {{PACKAGE}}.app import {{CLASS}}

    fullscreen = None
    if args.fullscreen:
        fullscreen = True
    elif args.windowed:
        fullscreen = False
    size = (args.width, args.height) if args.width and args.height else None

    app = {{CLASS}}(
        fullscreen=fullscreen,
        window_size=size,
        data_dir=args.data_dir or None,
    )
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

        set_process_name("{{PACKAGE}}")
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
