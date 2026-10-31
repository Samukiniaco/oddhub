"""CaVo — câmera que segue o T (centro + saidinha suave no movimento).

Anti-solavanco: o lead usa velocidade SUAVIZADA. A velocidade crua tem
dentes de serra (flap injeta -470 de vy a cada ~0,5s); somar isso direto na
visão dava saltos de 150px/frame. A base tem suavização própria e rápida.
"""
import pygame

from . import config as C

LEAD_SMOOTH = 2.5  # lead reage devagar (antecipa direção, ignora tranco)


class Camera:
    def __init__(self, vw, vh):
        self.vw = vw
        self.vh = vh
        self.bx = 0.0  # base suavizada (mundo)
        self.by = 0.0
        self.sv = pygame.Vector2(0, 0)  # velocidade suavizada (p/ o lead)
        self.x = 0.0   # canto superior-esquerdo da visão (mundo)
        self.y = 0.0

    def snap_to(self, pos):
        self.bx, self.by = pos.x, pos.y
        self.sv.update(0, 0)
        self._position(pygame.Vector2(0, 0))

    def resize(self, width, height):
        if (self.vw, self.vh) == (width, height):
            return
        self.vw, self.vh = width, height
        lead = self.sv * C.CAM_LEAD
        if lead.length() > C.CAM_LEAD_MAX:
            lead.scale_to_length(C.CAM_LEAD_MAX)
        self._position(lead)

    def follow(self, dt, target, vel):
        k = min(1.0, dt * C.CAM_SMOOTH)
        self.bx += (target.x - self.bx) * k
        self.by += (target.y - self.by) * k
        kl = min(1.0, dt * LEAD_SMOOTH)
        self.sv += (pygame.Vector2(vel) - self.sv) * kl
        lead = self.sv * C.CAM_LEAD
        if lead.length() > C.CAM_LEAD_MAX:
            lead.scale_to_length(C.CAM_LEAD_MAX)
        self._position(lead)

    def _position(self, lead):
        self.x = self.bx + lead.x - self.vw / 2
        self.y = self.by + lead.y - self.vh / 2
        self._clamp()

    def _clamp(self):
        m = 250.0  # deixa ver um pouco além da borda (brilho do limite)
        self.x = max(-m, min(C.WORLD_W - self.vw + m, self.x))
        self.y = max(-m, min(C.WORLD_H - self.vh + m, self.y))

    @property
    def off(self):
        return (self.x, self.y)
