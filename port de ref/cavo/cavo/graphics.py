"""Projeção uniforme: vetores são rasterizados na resolução real, sem ampliar um quadro fixo."""
from functools import lru_cache
import pygame
from . import config as C


class Geometry:
    def __init__(self, size):
        self.size = tuple(size)
        self.scale = min(size[0]/C.W, size[1]/C.H)
        self.world_size = (size[0]/self.scale, size[1]/self.scale)
        self.offset = ((size[0]-C.W*self.scale)/2, (size[1]-C.H*self.scale)/2)

    def ui_point(self, pos):
        return (pos[0]/self.scale, pos[1]/self.scale)

    def world_point(self, pos):
        return (pos[0]/self.scale, pos[1]/self.scale)


@lru_cache(maxsize=32)
def scaled_image(image, size, smooth, alpha):
    transform = pygame.transform.smoothscale if smooth else pygame.transform.scale
    return transform(image, size)


class ViewSurface:
    """Superfície lógica para desenho, com coordenadas de mundo ou da interface."""
    def __init__(self, surface, geometry, ui=False, smooth=False):
        self.surface = surface
        self.scale = geometry.scale
        self.offset = (0, 0)
        self.logical_size = geometry.world_size
        self.smooth = smooth

    def reference(self):
        """Painel de opções centralizado; HUD e menu raiz usam o viewport todo."""
        out = object.__new__(ViewSurface)
        out.__dict__ = self.__dict__.copy()
        out.offset = ((self.surface.get_width()-C.W*self.scale)/2,
                      (self.surface.get_height()-C.H*self.scale)/2)
        out.logical_size = (C.W, C.H)
        return out

    def hud(self, factor):
        out = object.__new__(ViewSurface)
        out.__dict__ = self.__dict__.copy()
        out.scale *= factor
        out.logical_size = (self.logical_size[0]/factor, self.logical_size[1]/factor)
        return out

    def point(self, pos):
        return (round(pos[0]*self.scale+self.offset[0]), round(pos[1]*self.scale+self.offset[1]))

    def rect(self, rect):
        x, y, w, h = rect
        left, top = self.point((x, y))
        right, bottom = self.point((x+w, y+h))
        return pygame.Rect(left, top, right-left, bottom-top)

    def get_size(self):
        return self.logical_size

    def get_width(self):
        return self.logical_size[0]

    def get_height(self):
        return self.logical_size[1]

    def set_clip(self, rect=None):
        self.surface.set_clip(self.rect(rect) if rect is not None else None)

    def get_clip(self):
        r = self.surface.get_clip()
        return pygame.Rect((r.x-self.offset[0])/self.scale, (r.y-self.offset[1])/self.scale,
                           r.w/self.scale, r.h/self.scale)

    def fill(self, color, rect=None):
        # Fundo preenche inclusive a área extra de telas largas/altas.
        return self.surface.fill(color, self.rect(rect) if rect is not None else None)

    def blit(self, image, dest):
        size = (max(1, round(image.get_width()*self.scale)), max(1, round(image.get_height()*self.scale)))
        if image.get_size() != size:
            if image.get_width()*image.get_height() <= 40000:
                image = scaled_image(image, size, self.smooth, image.get_alpha())
            else:
                transform = pygame.transform.smoothscale if self.smooth else pygame.transform.scale
                image = transform(image, size)
        return self.surface.blit(image, self.point(dest[:2]))


class ShapeDraw:
    def circle(self, s, color, center, radius, width=0):
        if isinstance(s, ViewSurface):
            center, radius, width = s.point(center), max(1, round(radius*s.scale)), self.width(s, width)
            s = s.surface
        return pygame.draw.circle(s, color, center, radius, width)

    def width(self, s, width):
        return max(1, round(width*s.scale)) if width else 0

    def rect(self, s, color, rect, width=0, **kwargs):
        if isinstance(s, ViewSurface):
            rect, width = s.rect(rect), self.width(s, width)
            kwargs = {k: max(0, round(v*s.scale)) for k, v in kwargs.items()}
            s = s.surface
        return pygame.draw.rect(s, color, rect, width, **kwargs)

    def polygon(self, s, color, points, width=0):
        if isinstance(s, ViewSurface):
            points, width = [s.point(p) for p in points], self.width(s, width)
            s = s.surface
        return pygame.draw.polygon(s, color, points, width)

    def line(self, s, color, start, end, width=1):
        if isinstance(s, ViewSurface):
            start, end, width = s.point(start), s.point(end), self.width(s, width)
            s = s.surface
        return pygame.draw.line(s, color, start, end, width)

    def ellipse(self, s, color, rect, width=0):
        if isinstance(s, ViewSurface):
            rect, width = s.rect(rect), self.width(s, width)
            s = s.surface
        return pygame.draw.ellipse(s, color, rect, width)

    def arc(self, s, color, rect, start, stop, width=1):
        if isinstance(s, ViewSurface):
            rect, width = s.rect(rect), self.width(s, width)
            s = s.surface
        return pygame.draw.arc(s, color, rect, start, stop, width)


draw = ShapeDraw()
