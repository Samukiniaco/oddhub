"""Janela/viewport e resolução interna; independente do canvas de referência da UI."""
import json
import math
import sys
import pygame
from .graphics import Geometry
from .input import browser_viewport


def render_size(preset, viewport, low_quality=False):
    """Mesmo orçamento de pixels; em qualidade baixa, corta pela metade."""
    aspect = viewport[0]/max(1, viewport[1])
    pixels = preset[0]*preset[1]
    if low_quality:
        pixels = pixels // 4  # corta resolução interna pela metade (2x em cada eixo)
    width = max(2, round(math.sqrt(pixels*aspect)/2)*2)
    height = max(2, round(width/aspect/2)*2)
    return width, height


class Display:
    def __init__(self, settings):
        self.st = settings
        self.web = sys.platform == "emscripten"
        self.viewport = settings.resolution
        if self.web:
            import platform
            self.viewport = tuple(json.loads(str(platform.window.cavoViewportSize())))
        self.screen = None
        self.canvas = None
        self.configure()

    def configure(self):
        st = self.st
        low_quality = st.quality == "low"
        if self.web:
            size = render_size(st.resolution, self.viewport, low_quality=low_quality)
            self.screen = pygame.display.set_mode(size)
            import platform
            platform.window.cavoSetDisplayMode(st.video_mode)
        elif st.video_mode == "window":
            # Alguns backends (KMSDRM/GBM em handhelds) nao suportam janela:
            # tenta redimensionavel primeiro (desktop) e cai para fullscreen
            # nativo em handhelds.
            driver = pygame.display.get_driver()
            sizes = pygame.display.get_desktop_sizes()
            native = sizes[0] if sizes else None
            if not native or native == (0, 0):
                native = st.resolution
            print("SDL driver:", driver, "desktop_sizes:", sizes, file=sys.stderr)
            self.screen = None
            for args in ((st.resolution, pygame.RESIZABLE),
                         (st.resolution,),
                         (native, pygame.FULLSCREEN),
                         (native, pygame.NOFRAME),
                         (native,)):
                try:
                    self.screen = pygame.display.set_mode(*args)
                    break
                except pygame.error as e:
                    print("set_mode", args, "->", e, file=sys.stderr)
                    continue
            if self.screen is None:
                self.screen = pygame.display.set_mode(native)
        else:
            sizes = pygame.display.get_desktop_sizes()
            native = sizes[0] if sizes else st.resolution
            flags = pygame.FULLSCREEN if st.video_mode == "fullscreen" else pygame.NOFRAME
            self.screen = None
            for args in ((native, flags), (native, pygame.FULLSCREEN), (native,)):
                try:
                    self.screen = pygame.display.set_mode(*args)
                    break
                except pygame.error:
                    continue
            if self.screen is None:
                self.screen = pygame.display.set_mode(native)
        self.update_canvas()
        st._dirty = False

    def update_canvas(self):
        low_quality = self.st.quality == "low"
        size = self.screen.get_size() if self.web else render_size(self.st.resolution, self.screen.get_size(), low_quality=low_quality)
        if self.canvas is None or self.canvas.get_size() != size:
            self.canvas = pygame.Surface(size)
        self.geometry = Geometry(size)
        self.st.actual_resolution = size

    def refresh(self):
        viewport = browser_viewport() if self.web else None
        if viewport and viewport != self.viewport:
            self.viewport = viewport
            self.st._dirty = True
        if self.st._dirty:
            self.configure()
        else:
            self.update_canvas()

    def ui_point(self, pos):
        sw, sh = self.screen.get_size()
        cw, ch = self.canvas.get_size()
        return self.geometry.ui_point((pos[0]*cw/sw, pos[1]*ch/sh))

    def world_point(self, pos):
        sw, sh = self.screen.get_size()
        cw, ch = self.canvas.get_size()
        return self.geometry.world_point((pos[0]*cw/sw, pos[1]*ch/sh))
