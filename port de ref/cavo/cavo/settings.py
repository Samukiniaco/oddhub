"""CaVo — opções de vídeo/gráficos persistidas em settings.json.

Modos de vídeo (bons p/ stream):
  Janela         -> window (resolução escolhida)
  Tela cheia     -> fullscreen exclusivo (resolução escolhida)
  Sem bordas     -> borderless, tamanho do monitor (ideal p/ capturar no OBS)
"""
import json
import os
import sys
from .controlmap import defaults, load_controls
from . import config as C

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "settings.json")

VIDEO_MODES = ("window", "fullscreen", "borderless")
VIDEO_LABELS = {"window": "Janela",
                "fullscreen": "Tela cheia",
                "borderless": "Sem bordas (stream)"}
OLD_RESOLUTIONS = [(960, 640), (1280, 720), (1600, 900), (1920, 1080)]
RESOLUTIONS = [(640, 360), (854, 480), (960, 540), (960, 640),
               (1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440), (3840, 2160)]
EXTRA_OPTIONS = ("show_fps", "debug_stats", "show_hints", "show_arrows", "show_minimap",
                 "show_timer", "show_bot_hud", "show_stamina")
VISUAL_LEVELS = {"particle_density": C.PARTICLE_DENSITY_VALUES, "bg_density": C.PARTICLE_DENSITY_VALUES,
                 "shake_strength": C.SHAKE_STRENGTH_VALUES, "hud_scale": C.HUD_SCALE_VALUES,
                 "touch_opacity": C.TOUCH_OPACITY_VALUES}


class Settings:
    def __init__(self):
        self.video_mode = "window"
        self.res_index = RESOLUTIONS.index((1280, 720))
        self.particles = True   # faíscas/ambiente (o rastro do jato é gameplay: sempre on)
        self.shake = True
        self.bg = True          # pontinhos do fundo
        self.relay = "ws://localhost:8765"  # relay do versus online
        self.online_mode = "nuvem"     # "nuvem" (Firebase) ou "relay" (servidor)
        self._dirty = False     # True -> main reconstrói a janela
        self.controls = defaults()
        self.smooth_scaling = sys.platform != "emscripten"  # web/APK privilegiam fluidez
        self.show_fps = False
        self.debug_stats = False
        self.quality = "custom"
        self.actual_resolution = None
        self.particle_density = 1.0
        self.bg_density = 1.0
        self.shake_strength = 1.0
        self.hud_scale = 1.0
        self.touch_opacity = 1.0
        self.show_hints = True
        self.show_arrows = True
        self.show_minimap = False
        self.show_timer = True
        self.show_bot_hud = True
        self.show_stamina = True

    @classmethod
    def load(cls):
        st = cls()
        try:
            if sys.platform == "emscripten":
                import platform
                raw = platform.window.localStorage.getItem("cavo.settings.v1")
                d = json.loads(str(raw)) if raw else {}
            else:
                with open(PATH, "r", encoding="utf-8") as f:
                    d = json.load(f)
            if not isinstance(d, dict):
                return st
            st.controls = load_controls(d.get("controls"))
            for key in ("smooth_scaling",) + EXTRA_OPTIONS:
                setattr(st, key, bool(d.get(key, getattr(st, key))))
            for key, choices in VISUAL_LEVELS.items():
                value = d.get(key)
                if value in choices:
                    setattr(st, key, value)
            if d.get("video_mode") in VIDEO_MODES:
                st.video_mode = d["video_mode"]
            if "res_index" in d:
                index = int(d["res_index"])
                if d.get("video_version", 1) < 2:
                    old = OLD_RESOLUTIONS[max(0, min(len(OLD_RESOLUTIONS)-1, index))]
                    st.res_index = RESOLUTIONS.index(old)
                else:
                    st.res_index = max(0, min(len(RESOLUTIONS)-1, index))
            if d.get("quality") in ("low", "medium", "high", "custom"):
                st.quality = d["quality"]
            st.particles = bool(d.get("particles", True))
            st.shake = bool(d.get("shake", True))
            st.bg = bool(d.get("bg", True))
            if isinstance(d.get("relay"), str) and d["relay"].startswith("ws://"):
                st.relay = d["relay"]
            if d.get("online_mode") in ("nuvem", "relay"):
                st.online_mode = d["online_mode"]
        except (OSError, ValueError, TypeError):
            pass
        return st

    def save(self):
        try:
            data = {"video_mode": self.video_mode, "res_index": self.res_index,
                    "video_version": 2, "quality": self.quality,
                    "particles": self.particles, "shake": self.shake,
                    "bg": self.bg, "relay": self.relay, "controls": self.controls,
                    "online_mode": self.online_mode,
                    "smooth_scaling": self.smooth_scaling, "show_fps": self.show_fps,
                    "debug_stats": self.debug_stats}
            data.update({key: getattr(self, key) for key in EXTRA_OPTIONS})
            data.update({key: getattr(self, key) for key in VISUAL_LEVELS})
            if sys.platform == "emscripten":
                import platform
                platform.window.localStorage.setItem("cavo.settings.v1", json.dumps(data))
                return
            with open(PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    @property
    def resolution(self):
        return RESOLUTIONS[self.res_index]

    def cycle_video(self):
        self.video_mode = VIDEO_MODES[(VIDEO_MODES.index(self.video_mode) + 1) % len(VIDEO_MODES)]
        self._dirty = True
        self.save()

    def cycle_res(self, direction=1):
        self.res_index = (self.res_index + direction) % len(RESOLUTIONS)
        self._dirty = True
        self.save()

    def cycle_quality(self, direction=1):
        modes = ("low", "medium", "high", "custom")
        self.quality = modes[(modes.index(self.quality)+direction) % len(modes)]
        if self.quality != "custom":
            self.particles = self.quality != "low"
            self.bg = self.quality != "low"
            self.shake = self.quality == "high"
            self.smooth_scaling = self.quality == "high"
            density = {"low": .25, "medium": .5, "high": 1.0}[self.quality]
            self.particle_density = self.bg_density = self.shake_strength = density
        self.save()

    def cycle_visual(self, key, direction=1):
        values = VISUAL_LEVELS[key]
        setattr(self, key, values[(values.index(getattr(self, key))+direction) % len(values)])
        if key in ("particle_density", "bg_density", "shake_strength"):
            self.quality = "custom"
        self.save()
