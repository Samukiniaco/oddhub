"""Audio com pygame.mixer.

Funciona com o pygame que ja vem no runtime do PortMaster. Se o aparelho
nao tiver mixer (ou o CFW nao tiver saida de audio), a classe continua
funcionando e apenas nao toca nada.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pygame


class Audio:
    """Efeitos e musica, com o mixer do pygame."""

    def __init__(self, volume: float = 0.6):
        self.volume = volume
        self.available = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._music: Optional[str] = None
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(8)
            self.available = True
        except pygame.error:
            self.available = False

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        if self.available:
            pygame.mixer.set_volume(self.volume)

    def load(self, name: str, path: Path) -> bool:
        """Carrega um efeito para tocar depois."""
        if not self.available or not Path(path).exists():
            return False
        try:
            self._sounds[name] = pygame.mixer.Sound(str(path))
            return True
        except pygame.error:
            return False

    def play(self, name: str, loops: int = 0, volume: Optional[float] = None) -> bool:
        """Toca um efeito carregado."""
        sound = self._sounds.get(name)
        if sound is None:
            return False
        sound.set_volume(self.volume if volume is None else volume)
        sound.play(loops=loops)
        return True

    def play_music(self, path: Path, loops: int = -1, volume: Optional[float] = None) -> bool:
        """Toca uma musica em loop."""
        if not self.available or not Path(path).exists():
            return False
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.volume if volume is None else volume)
            pygame.mixer.music.play(loops)
            self._music = str(path)
            return True
        except pygame.error:
            return False

    def stop_music(self, fade_ms: int = 400) -> None:
        if not self.available:
            return
        try:
            pygame.mixer.music.fadeout(max(0, fade_ms))
        except pygame.error:
            pass

    def shutdown(self) -> None:
        if not self.available:
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except pygame.error:
            pass
