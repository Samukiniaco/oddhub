"""Telemetria de desenvolvimento opt-in, em uma única chamada à ponte JS."""
import json
from .input import touch_state
from .controlmap import layout_for_view
from . import config as C


class BrowserDebug:
    def __init__(self, window):
        self.window = window
        self.enabled = bool(window.cavoDebug)
        self.frames = 0

    def report(self, game, source, screen, fps):
        if not self.enabled:
            return
        self.frames += 1
        self.window.cavoReport(json.dumps({
            "cavoState": game.state, "cavoInput": source,
            "cavoMenuIndex": game.mi, "cavoSection": game.section,
            "cavoAngle": float(game.players[0].angle),
            "cavoTouchJet": "jet" in touch_state()["btn"],
            "cavoTouchMode": game.st.controls["touch_mode"],
            "cavoScreenWidth": screen.get_width(), "cavoScreenHeight": screen.get_height(),
            "cavoFrames": self.frames, "cavoFPS": fps,
            "cavoSettingsTab": game.settings_menu.name,
            "cavoControlsPage": game.controls.page,
            "cavoShowFPS": game.st.show_fps,
            "cavoRenderWidth": (game.st.actual_resolution or screen.get_size())[0],
            "cavoRenderHeight": (game.st.actual_resolution or screen.get_size())[1],
            "cavoViewWidth": game.view_size[0], "cavoViewHeight": game.view_size[1],
            "cavoStaminaAlpha": game.players[0].stamina_alpha,
            "cavoRootRects": [list(r) for r in game.menu_rects],
            "cavoTouchLayout": layout_for_view(game.st.controls["touch_layout"], game.view_size),
            "cavoPanelOffset": [(game.view_size[0]-C.W)/2, (game.view_size[1]-C.H)/2],
            "cavoSettingsTop": game.settings_menu.top,
        }))
