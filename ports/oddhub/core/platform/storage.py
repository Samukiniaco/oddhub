"""Caminhos e conf do dispositivo (portável)."""
import os
import sys


def conf_dir(game_dir):
    """Diretório de configuração persistente (XDG_DATA_HOME no port)."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    d = os.path.join(base, os.path.basename(game_dir.rstrip(os.sep)))
    os.makedirs(d, exist_ok=True)
    return d


def game_dir():
    """Diretório do jogo (onde main.py está)."""
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def bind_directories(src, dst):
    """No-op seguro em desktop; PortMaster fornece a real."""
    try:
        if os.path.isdir(src) and not os.path.islink(src):
            pass
    except OSError:
        pass
    return True