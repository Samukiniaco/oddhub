"""Saída do aplicativo: Activity Android, janela desktop ou tela final no web."""
import sys
import pygame
from .texts import T


def quit_game():
    if sys.platform == "emscripten":
        import platform
        platform.window.cavoQuit(T("menu.closed"), T("menu.restart"))
    pygame.quit()
    raise SystemExit
