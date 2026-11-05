"""Entry point do port PortMail.

Uso:
    python main.py                 # modo demo (offline), janela
    python main.py --backend imap  # tenta conectar via IMAP/SMTP
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
    here = os.path.dirname(os.path.abspath(__file__))       # .../gmail/gmail
    port_root = os.path.dirname(here)                       # .../gmail
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
    parser = argparse.ArgumentParser(prog="portmail", description="PortMail para PortMaster")
    parser.add_argument(
        "--backend",
        choices=("demo", "imap"),
        default=None,
        help="backend de email (imap = real)",
    )
    parser.add_argument("--demo", action="store_true", help="força o modo demo offline")
    parser.add_argument("--fullscreen", action="store_true", help="inicia em tela cheia")
    parser.add_argument("--windowed", action="store_true", help="força modo janela")
    parser.add_argument("--width", type=int, default=0, help="largura da janela")
    parser.add_argument("--height", type=int, default=0, help="altura da janela")
    parser.add_argument("--data-dir", default="", help="pasta de dados alternativa")
    parser.add_argument("--selftest", action="store_true", help="roda testes rápidos e sai")
    return parser.parse_args(argv)


def _selftest() -> int:
    """Exercita store + backend demo sem precisar de display."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from gmail import config
    from gmail.backend import make_backend
    from gmail.store import Store

    data_dir = config.data_dir()
    store = Store(data_dir / "selftest.sqlite3")
    try:
        backend = make_backend("demo", store, data_dir)
        backend.start()
        emails = backend.emails()
        assert emails, "backend demo não criou emails"
        email = emails[0]
        assert email.id, "email sem id"
        print("selftest ok")
        print(f"  dados: {data_dir}")
        print(f"  emails: {len(backend.emails())}")
        print(f"  conta: {backend.default_account().display_name() if backend.default_account() else 'nenhuma'}")
        return 0
    finally:
        try:
            backend.stop()  # type: ignore[possibly-undefined]
        except Exception:
            pass
        store.close()


def _run_gui(args) -> int:
    from gmail.ui.app import App

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
