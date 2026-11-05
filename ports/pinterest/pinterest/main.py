"""Entry point do port Pinterest.

Uso:
    python main.py                 # modo demo (offline), janela
    python main.py --backend api   # API real do Pinterest (requer token)
    python main.py --fullscreen    # handheld / PortMaster
    python main.py --selftest      # testa store + backend demo sem abrir tela
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback


def _bootstrap() -> None:
    """Ajusta sys.path para funcionar no repo e no zip do PortMaster."""
    here = os.path.dirname(os.path.abspath(__file__))       # .../pinterest/pinterest
    port_root = os.path.dirname(here)                       # .../pinterest
    sys.path.insert(0, port_root)

    # core vendorizado (opcional neste port)
    vendored_core = os.path.join(port_root, "core")
    repo_root = os.path.dirname(os.path.dirname(port_root))
    if os.path.isdir(vendored_core):
        sys.path.insert(0, port_root)
    elif os.path.isdir(os.path.join(repo_root, "core")):
        sys.path.insert(0, repo_root)

    # dependências baixadas com fetch_deps.py
    site = os.path.join(port_root, "site-packages")
    if os.path.isdir(site):
        sys.path.insert(0, site)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="pinterest", description="Pinterest para PortMaster")
    parser.add_argument(
        "--backend",
        choices=("demo", "api"),
        default=None,
        help="backend de pins (api = real)",
    )
    parser.add_argument("--demo", action="store_true", help="força o modo demo offline")
    parser.add_argument("--fullscreen", action="store_true", help="inicia em tela cheia")
    parser.add_argument("--windowed", action="store_true", help="força modo janela")
    parser.add_argument("--width", type=int, default=0, help="largura da janela")
    parser.add_argument("--height", type=int, default=0, help="altura da janela")
    parser.add_argument("--data-dir", default="", help="pasta de dados alternativa")
    parser.add_argument("--token", default="", help="token da API do Pinterest")
    parser.add_argument("--selftest", action="store_true", help="roda testes rápidos e sai")
    return parser.parse_args(argv)


def _selftest() -> int:
    """Exercita store + backend demo sem precisar de display."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from pinterest import config
    from pinterest.backend import make_backend
    from pinterest.store import Store

    data_dir = config.data_dir()
    store = Store(data_dir / "selftest.sqlite3")
    try:
        backend = make_backend("demo", store, data_dir)
        backend.start()
        boards = backend.boards()
        pins = backend.pins()
        assert boards, "backend demo não criou boards"
        assert pins, "backend demo não criou pins"
        pin = pins[0]
        assert pin.id and pin.title, "pin inválido"
        # busca
        hits = backend.search(pins[0].title.split()[0])
        assert hits, "busca não encontrou nada"
        # salvar
        backend.toggle_save(pin.id)
        saved = store.get_pin(pin.id)
        assert saved and saved.is_saved, "toggle_save falhou"
        backend.toggle_save(pin.id)
        print("selftest ok")
        print(f"  dados: {data_dir}")
        print(f"  boards: {len(boards)} · pins: {len(pins)}")
        print(f"  busca por '{pins[0].title.split()[0]}': {len(hits)} resultado(s)")
        return 0
    finally:
        try:
            backend.stop()  # type: ignore[possibly-undefined]
        except Exception:
            pass
        store.close()


def _run_gui(args) -> int:
    from pinterest.ui.app import App

    backend = args.backend
    if args.demo:
        backend = "demo"

    fullscreen = None
    if args.fullscreen:
        fullscreen = True
    elif args.windowed:
        fullscreen = False

    size = None
    if args.width and args.height:
        size = (args.width, args.height)

    data_dir = args.data_dir or None
    app = App(
        backend_kind=backend,
        fullscreen=fullscreen,
        window_size=size,
        data_dir=data_dir,
    )
    if args.token:
        app.backend.set_token(args.token)
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
        try:
            import time

            time.sleep(4)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
