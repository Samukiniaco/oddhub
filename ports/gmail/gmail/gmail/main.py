"""Ponto de entrada do port Gmail.

    python3 -m gmail                 # modo demo, janela
    python3 -m gmail --backend imap  # conta real (IMAP/SMTP)
    python3 -m gmail --fullscreen    # handheld / PortMaster
    python3 -m gmail --selftest      # teste sem abrir tela
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback

# Permite rodar como script (python gmail/main.py) e como modulo (python -m gmail).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _set_process_name(name: str = "gmail") -> None:
    """Nomeia o processo para o gptokeyb2 encontrar (kill switch Select+Start).

    O interpretador vem do runtime do PortMaster e o nome dele varia
    (python3, python3.11...). Fixar o nome do processo deixa o alvo do
    gptokeyb2 estavel: sempre "gmail".
    """
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(15, name.encode("utf-8"), 0, 0, 0)  # PR_SET_NAME
    except Exception:
        pass


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="gmail", description="Cliente de email para PortMaster")
    parser.add_argument("--backend", choices=("demo", "imap"), default=None, help="modo de operacao")
    parser.add_argument("--demo", action="store_true", help="forca o modo demo offline")
    parser.add_argument("--fullscreen", action="store_true", help="abre em tela cheia")
    parser.add_argument("--windowed", action="store_true", help="forca janela (testes no PC)")
    parser.add_argument("--width", type=int, default=0, help="largura da janela")
    parser.add_argument("--height", type=int, default=0, help="altura da janela")
    parser.add_argument("--data-dir", default="", help="pasta de dados alternativa")
    parser.add_argument("--selftest", action="store_true", help="roda os testes rapidos e sai")
    return parser.parse_args(argv)


def _selftest() -> int:
    """Testa store e backend demo sem abrir display."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from gmail import config
    from gmail.backend import make_backend
    from gmail.store import Store

    data_dir = config.data_dir()
    store = Store(data_dir / "selftest.sqlite3")
    backend = None
    try:
        backend = make_backend("demo", store, data_dir)
        backend.start()
        accounts = backend.accounts()
        emails = backend.emails()
        assert accounts, "nenhuma conta no modo demo"
        assert emails, "nenhum email no modo demo"

        first = emails[0]
        found = backend.search(accounts[0].id, first.subject.split()[0])
        assert found, "busca nao encontrou o email"

        backend.toggle_star(first.id)
        assert backend.email(first.id).is_starred, "toggle_star falhou"
        backend.toggle_star(first.id)

        sent = backend.send(["teste@example.com"], "Assunto de teste", "Corpo de teste")
        assert sent is not None, "envio no modo demo falhou"
        assert sent.folder == "SENT", "email enviado nao foi para SENT"

        print("selftest ok")
        print(f"  dados: {data_dir}")
        print(f"  contas: {len(accounts)}")
        print(f"  emails: {len(backend.emails())}")
        return 0
    finally:
        if backend is not None:
            try:
                backend.stop()
            except Exception:
                pass
        store.close()


def _run_gui(args) -> int:
    from gmail.ui.app import App

    backend = "demo" if args.demo else args.backend
    fullscreen = None
    if args.fullscreen:
        fullscreen = True
    elif args.windowed:
        fullscreen = False
    size = (args.width, args.height) if args.width and args.height else None
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
    _set_process_name()
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
