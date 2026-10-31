"""CaVo — partida, HUD limpo estilo Osu! e menu XMB.

Estados: menu | treino | versus | over.
Mundo grande com câmera (split-screen no versus). Textos com auto-fit.
update recebe Intents (cavo/input.py). Menu por teclado e mouse (hover+clique).
"""
import math
import random
import sys
from functools import lru_cache

import pygame

from . import config as C
from . import net
from .arena import Balloon
from .camera import Camera
from .particles import Jet, Spark
from .player import Player, wrap_angle
from .sprites import path_for_slot
from .texts import T
from .controls_menu import ControlsMenu, draw_touch
from .settings_menu import SettingsMenu
from .graphics import draw, Geometry, ViewSurface

ONLINE_OK = sys.platform != "emscripten"  # browser: sem socket/requests

MENU_ROOT = ["menu.treino", "menu.versus", "menu.online", "menu.settings", "menu.sair"]
MENU_KINDS = ["treino", "versus", "online", "settings", "sair"]
MENU_DESCS = ["menu.desc_treino", "menu.desc_versus", "menu.desc_online",
              "menu.desc_settings", "menu.desc_sair"]
MENU_COLORS = {"treino": C.CYAN, "versus": C.ORANGE, "online": (120, 255, 170),
               "settings": (150, 170, 255), "sair": (255, 120, 120)}


def root_kinds():
    kinds = list(MENU_KINDS)
    if not ONLINE_OK:
        kinds.remove("online")
    return kinds
GFX_ROWS = ["menu.row_video", "menu.row_res", "menu.row_part",
            "menu.row_shake", "menu.row_bg", "settings.smooth", "settings.quality",
            "settings.particle_density", "settings.bg_density", "settings.shake_strength",
            "settings.hud_scale", "settings.touch_opacity", "menu.row_back"]
VISUAL_ROW_KEYS = ("particle_density", "bg_density", "shake_strength", "hud_scale", "touch_opacity")

_font_cache = {}
_font_meta = {}


def get_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("consolas", size, bold=bold)
        _font_meta[_font_cache[key]] = key
    return _font_cache[key]


@lru_cache(maxsize=C.TEXT_CACHE_SIZE)
def fit_font(text, max_w, size, bold=False):
    """Ajustador automático: encolhe a fonte até caber em max_w."""
    s = size
    while s > 10:
        f = get_font(s, bold)
        if f.size(text)[0] <= max_w:
            return f
        s -= 2
    return get_font(10, bold)


@lru_cache(maxsize=C.TEXT_CACHE_SIZE)
def rendered_text(font, text, color):
    return font.render(text, True, color)


def hp_color(pct):
    if pct > 0.5:
        k = (pct - 0.5) * 2
        return (int(255 * (1 - k)), 220, 80)
    k = max(0.0, pct * 2)
    return (255, int(80 + 140 * k), 80)


# ---------- Culling espacial (otimiza render por software) ----------
# Margem extra para evitar cortar elementos no limite
CULL_MARGIN = 120

def in_viewport(x, y, vx, vy, vw, vh, margin=CULL_MARGIN):
    """True se o ponto (ou objeto pequeno) pode ser visível na viewport."""
    return (vx - margin < x < vx + vw + margin) and (vy - margin < y < vy + vh + margin)


class Game:
    def __init__(self, settings):
        self.st = settings
        self.players = [Player(C.SPAWN_P1, C.CYAN, "P1", 0, path_for_slot("p1")),
                        Player(C.SPAWN_P2, C.ORANGE, "P2", 1, path_for_slot("p2"))]
        self.jets = []
        self.charged = []
        self.sparks = []
        self.balloons = []
        self.floaters = []
        self.cam_full = Camera(C.W, C.H)
        self.cam1 = Camera(C.W // 2, C.H)
        self.cam2 = Camera(C.W // 2, C.H)
        self.view_size = (C.W, C.H)
        self.state = "menu"
        self.last_mode = "treino"
        self.section = "root"  # root | gfx | online | treino
        self.mi = 0
        self.gi = 0
        self.menu_rects = []
        self.gfx_rects = []
        self.controls = ControlsMenu(settings)
        self.settings_menu = SettingsMenu(self)
        self.touch_visible = False
        # --- treino (seção: balões | labirinto | bots) ---
        self.tpage = "mode"    # mode | maze_opt | bots_opt
        self.tmode = "baloes"
        self.tfocus = 0
        self.trow_rects = []
        self.mdiff = "normal"
        self.nbots = 1
        self.botskill = "normal"
        self.tmaze = None
        self.mlevel = 1
        self.mtime = 0.0
        self.mtotal = 0.0
        self.mcp = 0
        self.tbots = []
        self.brains = []
        # --- online (seção) ---
        self.opage = "main"    # main | create | join | list | lobby
        self.ofields = {"relay": settings.relay, "modo": getattr(settings, "online_mode", "nuvem"),
                        "sala": "Sala do Samuka",
                        "nome": "P1", "senha": "", "tag": "", "codigo": ""}
        self.ofocus = 0
        self.orooms = []
        self.oroom_sel = 0
        self.olobby = None     # {"role": "host"|"guest", "code": ...}
        self.omsg = ""
        self.opoll_t = 0.0
        self.ohb_t = 0.0
        self.relay_state = (False, False, 0.0, "")
        self._relay_checking = False
        self._relay_t = 0.0
        self.cloud_state = (False, False, "")   # (checado, ok, erro) da nuvem
        self._cloud_checking = False
        self._cloud_t = 0.0
        # --- online (partida) ---
        self.online = None     # OnlineSession
        self.o_you = 0
        self.o_local = None
        self.o_foe = None
        self.ghost_ok = False
        self.oacc = 0.0        # acumulador 20Hz p/ inputs
        self.oseq = 0
        self.oping_t = 0.0
        self.ofell_sent = False
        self.score = 0
        self.disp_score = 0
        self.combo = 0
        self.combo_pop = 0.0
        self.max_combo = 0
        self.time = 0.0
        self.winner = ""
        self.winner_sub = ""
        self.shake = 0.0
        self.font = get_font(20)
        self.f_sm = get_font(15)
        self.f_score = get_font(34, True)
        self.f_combo = get_font(40, True)
        self.big = get_font(44, True)

    # ================= fluxo =================
    def reset(self, mode):
        self.state = mode
        self.last_mode = mode
        self.jets = []
        self.charged = []
        self.sparks = []
        self.floaters = []
        self.score = 0
        self.disp_score = 0
        self.combo = 0
        self.combo_pop = 0.0
        self.max_combo = 0
        self.time = 0.0
        self.winner = ""
        self.winner_sub = ""
        self.shake = 0.0
        if mode == "treino":
            self.start_treino(getattr(self, "tmode", "baloes"))
        else:
            self.players[0].spawn = pygame.Vector2(C.SPAWN_P1)
            self.players[1].spawn = pygame.Vector2(C.SPAWN_P2)
            for pl in self.players:
                pl.reset()
            self.balloons = []
            self.cam1.snap_to(self.players[0].p)
            self.cam2.snap_to(self.players[1].p)

    def start_treino(self, tmode):
        """(Re)começa o treino no modo pedido, zerando o cenário."""
        from .bots import Brain
        from .maze import Maze
        self.tmode = tmode
        self.jets = []
        self.charged = []
        self.sparks = []
        self.floaters = []
        self.score = 0
        self.disp_score = 0
        self.combo = 0
        self.combo_pop = 0.0
        self.max_combo = 0
        self.time = 0.0
        self.winner = ""
        self.winner_sub = ""
        self.shake = 0.0
        self.tbots = []
        self.brains = []
        self.tmaze = None
        p = self.players[0]
        if tmode == "labirinto":
            self.tmaze = Maze(self.mdiff)
            p.spawn = self.tmaze.start.copy()
            p.reset()
            self.balloons = []
            self.mlevel = 1
            self.mtime = 0.0
            self.mtotal = 0.0
            self.mcp = 0
        elif tmode == "bots":
            p.spawn = pygame.Vector2(C.WORLD_W / 2 - 600, 500)
            p.reset()
            self.balloons = []
            spots = [(C.WORLD_W / 2 + 600, 500), (C.WORLD_W / 2, 300),
                       (C.WORLD_W / 2, 900), (C.WORLD_W / 2 - 200, 1100),
                       (C.WORLD_W / 2 + 200, 150)]
            cols = [C.ORANGE, (150, 180, 255), (140, 255, 160),
                    (200, 120, 255), (255, 150, 220)]
            for i in range(max(1, min(C.BOT_MAX, self.nbots))):
                b = Player(spots[i], cols[i % 3], T("modos.bot_name").format(n=i + 1),
                           2 + i, None)
                b.reset()
                self.tbots.append(b)
                self.brains.append(Brain(self.botskill))
        else:
            p.spawn = pygame.Vector2(C.SPAWN_TREINO)
            p.reset()
            self.balloons = [Balloon(near=p.p) for _ in range(C.BALLOON_COUNT)]
        self.cam_full.snap_to(p.p)
        self.state = "treino"
        self.last_mode = "treino"

    def retry_maze_level(self):
        """R no labirinto: labirinto novo, mesmo nível (zera o relógio da fase)."""
        from .maze import Maze
        self.tmaze = Maze(self.mdiff)
        p = self.players[0]
        p.p = self.tmaze.start.copy()
        p.v *= 0
        p.inv = 1.0
        self.jets = []
        self.charged = []
        self.mcp = 0
        self.mtime = 0.0

    def fighters(self):
        """Todos que lutam no estado atual (dono do tiro conta p/ abate)."""
        if self.state == "treino":
            if self.tmode == "bots":
                return [self.players[0]] + self.tbots
            return self.players[:1]
        return self.players

    def active_players(self):
        return self.fighters()

    def _credit(self, idx):
        for pl in self.fighters():
            if pl.idx == idx:
                pl.kills += 1
                return

    def floater(self, x, y, text, color, font=None, life=0.9):
        self.floaters.append({"p": pygame.Vector2(x, y), "text": text,
                              "color": color, "font": font or self.font, "life": life, "max": life})

    # ================= menu XMB =================
    def esc_menu(self):
        if self.section == "settings":
            if not self.settings_menu.key(pygame.K_ESCAPE):
                self.section = "root"
            return True
        if self.section == "controls":
            if not self.controls.back():
                self.section = "root"
            return True
        if self.section == "gfx":
            self.section = "root"
            return True
        if self.section == "online":
            self.online_back()
            return True
        if self.section == "treino":
            self.treino_back()
            return True
        return False

    def gfx_value(self, i):
        if i == 0:
            from .settings import VIDEO_LABELS
            return VIDEO_LABELS[self.st.video_mode]
        if i == 1:
            w, h = self.st.actual_resolution or self.st.resolution
            return f"{w}x{h}"
        if i == 2:
            return "on" if self.st.particles else "off"
        if i == 3:
            return "on" if self.st.shake else "off"
        if i == 4:
            return "on" if self.st.bg else "off"
        if i == 5:
            return T("settings.smooth_on" if self.st.smooth_scaling else "settings.smooth_off")
        if i == 6:
            return T("settings.quality_"+self.st.quality)
        if 7 <= i < 12:
            return f"{getattr(self.st, VISUAL_ROW_KEYS[i-7])*100:.0f}%"
        return ""

    def gfx_adjust(self, i, direction=1):
        if i == 0:
            from .settings import VIDEO_MODES
            modes = VIDEO_MODES
            self.st.video_mode = modes[(modes.index(self.st.video_mode) + direction) % len(modes)]
            self.st._dirty = True
        elif i == 1:
            self.st.cycle_res(direction)
            return
        elif i == 2:
            self.st.particles = not self.st.particles
        elif i == 3:
            self.st.shake = not self.st.shake
        elif i == 4:
            self.st.bg = not self.st.bg
        elif i == 5:
            self.st.smooth_scaling = not self.st.smooth_scaling
        elif i == 6:
            self.st.cycle_quality(direction)
            return
        elif 7 <= i < 12:
            self.st.cycle_visual(VISUAL_ROW_KEYS[i-7], direction)
            return
        elif i == 12:
            self.section = "root"
            return
        if i in (2, 3, 4, 5):
            self.st.quality = "custom"
        self.st.save()

    def handle_menu_key(self, key):
        if self.section == "settings":
            if not self.settings_menu.key(key):
                self.section = "root"
            return None
        n = len(root_kinds())
        if self.section == "root":
            if key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP):
                self.mi = (self.mi - 1) % n
            elif key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN):
                self.mi = (self.mi + 1) % n
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                return self.activate_root(self.mi)
            elif key == pygame.K_1:
                return self.activate_root(0)
            elif key == pygame.K_2:
                return self.activate_root(1 % n)
            elif key == pygame.K_3:
                return self.activate_root(2 % n)
        elif self.section == "gfx":
            if key == pygame.K_UP:
                self.gi = (self.gi - 1) % len(GFX_ROWS)
            elif key == pygame.K_DOWN:
                self.gi = (self.gi + 1) % len(GFX_ROWS)
            elif key == pygame.K_LEFT:
                self.gfx_adjust(self.gi, -1)
            elif key in (pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE):
                self.gfx_adjust(self.gi, 1)
        return None

    def activate_root(self, i):
        kinds = root_kinds()
        kind = kinds[i % len(kinds)]
        if kind == "treino":
            self.section = "treino"
            self.tpage = "mode"
            self.tfocus = 0
        elif kind == "versus":
            self.reset("versus")
        elif kind == "online":
            self.section = "online"
            self.opage = "main"
            self.ofocus = 0
            self.omsg = ""
        elif kind == "settings":
            self.section = "settings"
            self.settings_menu.open()
        elif kind == "sair":
            return "quit"
        return None

    def menu_hover(self, pos):
        """Mouse por cima foca o item (XMB navegável sem teclado)."""
        x, y = pos
        if self.section == "settings":
            self.settings_menu.hover(self.panel_point(pos))
            return
        if self.section != "root":
            pos = self.panel_point(pos)
            x, y = pos
        if self.section == "controls":
            self.controls.hover(pos)
            return
        if self.section == "root":
            for i, r in enumerate(self.menu_rects):
                if r.collidepoint(x, y):
                    self.mi = i
                    break
        elif self.section == "gfx":
            for i, r in enumerate(self.gfx_rects):
                if r.collidepoint(x, y):
                    self.gi = i
                    break
        elif self.section == "online":
            for kind, i, r in getattr(self, "orow_rects", []):
                if r.collidepoint(x, y):
                    if kind == "focus":
                        self.ofocus = i
                    else:
                        self.oroom_sel = i
                    break
        elif self.section == "treino":
            for _kind, i, r in getattr(self, "trow_rects", []):
                if r.collidepoint(x, y):
                    self.tfocus = i
                    break

    def menu_click(self, pos):
        x, y = pos
        if self.section == "settings":
            self.settings_pointer("down", "mouse", pos)
            return None
        if self.section != "root":
            pos = self.panel_point(pos)
            x, y = pos
        if self.section == "controls":
            if not self.controls.pointer("down", "mouse", pos):
                self.section = "root"
            return None
        if self.section == "root":
            for i, r in enumerate(self.menu_rects):
                if r.collidepoint(x, y):
                    self.mi = i
                    return self.activate_root(i)
        elif self.section == "gfx":
            for i, r in enumerate(self.gfx_rects):
                if r.collidepoint(x, y):
                    self.gi = i
                    self.gfx_adjust(i, 1)
                    break
        elif self.section == "online":
            for kind, i, r in getattr(self, "orow_rects", []):
                if r.collidepoint(x, y):
                    if kind == "focus":
                        self.ofocus = i
                        items = self._oitems()
                        if i < len(items) and items[i][0] == "btn":
                            items[i][2]()
                        elif i < len(items) and items[i][0] == "opt":
                            self._o_mode(1)
                    else:
                        self.oroom_sel = i
                        if self.orooms:
                            code = self.orooms[i % len(self.orooms)][0]
                            self.ofields["codigo"] = code
                            self.opage = "join"
                            self.ofocus = 1
                    break
        elif self.section == "treino":
            for kind, i, r in getattr(self, "trow_rects", []):
                if r.collidepoint(x, y):
                    if kind == "mode":
                        self.tfocus = i
                        self._tmode_go(i)
                    elif kind == "back":
                        self.treino_back()
                    else:
                        self.tfocus = i
                        self._topt_activate(i)
                    break
        return None

    def settings_pointer(self, kind, fid, pos):
        if not self.settings_menu.pointer(kind, fid, self.panel_point(pos)):
            self.section = "root"

    def panel_point(self, pos):
        if self.section == "settings" and self.controls.page == "layout" and self.settings_menu.name == "controls":
            return pos
        return (pos[0]-(self.view_size[0]-C.W)/2, pos[1]-(self.view_size[1]-C.H)/2)

    # ================= treino: submenu =================
    TMODES = ["baloes", "labirinto", "bots"]
    TDIFFS = ["facil", "normal", "dificil"]

    def _tmode_go(self, i):
        if i < len(self.TMODES):
            m = self.TMODES[i]
            if m == "baloes":
                self.start_treino("baloes")
            elif m == "labirinto":
                self.tpage = "maze_opt"
                self.tfocus = 0
            elif m == "bots":
                self.tpage = "bots_opt"
                self.tfocus = 0
        else:
            self.treino_back()

    def _topt_items(self):
        if self.tpage == "maze_opt":
            return [("dif", T("modos.dificuldade") + ": " + T("modos.dif_" + self.mdiff)),
                    ("go", T("modos.jogar")),
                    ("back", T("modos.m_voltar"))]
        if self.tpage == "bots_opt":
            return [("n", f"{T('modos.nbots')}: {self.nbots}"),
                    ("skill", T("modos.skill") + ": " + T("modos.dif_" + self.botskill)),
                    ("go", T("modos.jogar")),
                    ("back", T("modos.m_voltar"))]
        return []

    def _topt_adjust(self, i, direction=1):
        if self.tpage == "maze_opt":
            at = (self.TDIFFS.index(self.mdiff) + direction) % len(self.TDIFFS)
            self.mdiff = self.TDIFFS[at]
        elif self.tpage == "bots_opt":
            if i == 0:
                self.nbots = ((self.nbots - 1 + direction) % C.BOT_MAX) + 1
            elif i == 1:
                at = (self.TDIFFS.index(self.botskill) + direction) % len(self.TDIFFS)
                self.botskill = self.TDIFFS[at]

    def _topt_activate(self, i):
        items = self._topt_items()
        if i >= len(items):
            return
        kind = items[i][0]
        if kind == "go":
            if self.tpage == "maze_opt":
                self.start_treino("labirinto")
            else:
                self.start_treino("bots")
        elif kind == "back":
            self.treino_back()
        else:
            self._topt_adjust(i, 1)

    def treino_back(self):
        if self.tpage in ("maze_opt", "bots_opt"):
            self.tpage = "mode"
        else:
            self.section = "root"
        self.tfocus = 0

    def treino_key(self, ev):
        if ev.key == pygame.K_ESCAPE:
            self.treino_back()
            return None
        if self.tpage == "mode":
            n = len(self.TMODES) + 1
            if ev.key == pygame.K_UP:
                self.tfocus = (self.tfocus - 1) % n
            elif ev.key == pygame.K_DOWN:
                self.tfocus = (self.tfocus + 1) % n
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.tfocus == n - 1:
                    self.treino_back()
                else:
                    self._tmode_go(self.tfocus)
            return None
        items = self._topt_items()
        if ev.key == pygame.K_UP:
            self.tfocus = (self.tfocus - 1) % len(items)
        elif ev.key == pygame.K_DOWN:
            self.tfocus = (self.tfocus + 1) % len(items)
        elif ev.key == pygame.K_LEFT:
            if items and items[self.tfocus][0] != "go":
                self._topt_adjust(self.tfocus, -1)
        elif ev.key == pygame.K_RIGHT:
            if items and items[self.tfocus][0] != "go":
                self._topt_adjust(self.tfocus, 1)
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._topt_activate(self.tfocus)
        return None

    # ================= online: menu =================
    OFIELD_MAX = {"relay": 40, "sala": 30, "nome": 16, "senha": 24, "tag": 20, "codigo": 12}
    OFIELD_TXT = {"relay": "online.f_relay", "modo": "online.f_modo",
                  "sala": "online.f_sala", "nome": "online.f_nome",
                  "senha": "online.f_senha", "tag": "online.f_tag", "codigo": "online.f_codigo"}
    ON_MODES = ("nuvem", "relay")

    def _o_mode(self, direction=1):
        """Alterna entre nuvem (Firebase) e relay (servidor próprio)."""
        modo = self.ofields.get("modo", "nuvem")
        if modo not in self.ON_MODES:
            modo = "nuvem"
        self.ofields["modo"] = self.ON_MODES[(self.ON_MODES.index(modo) + direction) % len(self.ON_MODES)]
        self.st.online_mode = self.ofields["modo"]
        try:
            self.st.save()
        except Exception:
            pass
        self.omsg = ""
        itens = self._oitems()
        if self.ofocus >= len(itens):
            self.ofocus = max(0, len(itens) - 1)

    def _o_mode_label(self):
        return T("online.modo_nuvem") if self.ofields.get("modo") == "nuvem" else T("online.modo_relay")

    def _oitems(self):
        if self.opage == "main":
            itens = [("opt", "modo")]
            if self.ofields.get("modo") != "nuvem":
                itens.append(("text", "relay"))   # só o relay usa esse campo
            return itens + [("btn", T("online.b_criar"), self._o_goto_create),
                            ("btn", T("online.b_entrar"), self._o_goto_join),
                            ("btn", T("online.b_lista"), self._o_goto_list)]
        if self.opage == "create":
            return [("text", "sala"), ("text", "nome"), ("text", "senha"),
                    ("text", "tag"), ("btn", T("online.b_CRIAR"), self._o_create)]
        if self.opage == "join":
            return [("text", "codigo"), ("text", "nome"), ("text", "senha"),
                    ("btn", T("online.b_ENTRAR"), self._o_join)]
        if self.opage == "lobby":
            return [("btn", "JOGAR", self._o_play)] if self._lobby_ready() else []
        return []

    def online_back(self):
        if self.opage == "lobby":
            self._leave_lobby()
            self.opage = "main"
        elif self.opage in ("create", "join", "list"):
            self.opage = "main"
        else:
            self.section = "root"
        self.ofocus = 0
        self.omsg = ""

    def online_key(self, ev):
        """Teclado na seção Online (texto + botões)."""
        if ev.key == pygame.K_ESCAPE:
            self.online_back()
            return None
        if self.opage == "list":
            if ev.key == pygame.K_UP:
                self.oroom_sel = (self.oroom_sel - 1) % max(1, len(self.orooms))
            elif ev.key == pygame.K_DOWN:
                self.oroom_sel = (self.oroom_sel + 1) % max(1, len(self.orooms))
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE) and self.orooms:
                code = self.orooms[self.oroom_sel % len(self.orooms)][0]
                self.ofields["codigo"] = code
                self.opage = "join"
                self.ofocus = 1
            elif ev.key == pygame.K_r:
                self._o_refresh_list()
            return None
        if self.opage == "lobby":
            if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._o_play()
            return None
        items = self._oitems()
        if not items:
            return None
        n = len(items)
        if ev.key == pygame.K_UP:
            self.ofocus = (self.ofocus - 1) % n
        elif ev.key == pygame.K_DOWN:
            self.ofocus = (self.ofocus + 1) % n
            return None
        kind = items[self.ofocus][0]
        if kind == "opt":
            if ev.key == pygame.K_LEFT:
                self._o_mode(-1)
            elif ev.key == pygame.K_RIGHT:
                self._o_mode(1)
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._o_mode(1)
            return None
        if kind == "text":
            k = items[self.ofocus][1]
            if ev.key == pygame.K_BACKSPACE:
                self.ofields[k] = self.ofields[k][:-1]
            elif ev.key in (pygame.K_RETURN, pygame.K_TAB):
                self.ofocus = (self.ofocus + 1) % n
            elif ev.unicode and ev.unicode.isprintable() and len(self.ofields[k]) < self.OFIELD_MAX[k]:
                self.ofields[k] += ev.unicode
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
            items[self.ofocus][2]()
        return None

    def _o_goto_create(self):
        self.opage = "create"
        self.ofocus = 0
        self.omsg = ""

    def _o_goto_join(self):
        self.opage = "join"
        self.ofocus = 0
        self.omsg = ""

    def _o_goto_list(self):
        self._o_refresh_list()

    def _o_refresh_list(self):
        try:
            try:
                net.cleanup_stale()
            except Exception:
                pass
            self.orooms = net.list_rooms()
            self.oroom_sel = 0
            self.opage = "list"
            self.omsg = f"{len(self.orooms)} sala(s)" if self.orooms else "nenhuma sala — crie uma!"
        except Exception as e:
            self.omsg = str(e)

    def _o_create(self):
        try:
            code = net.create_room(self.ofields["sala"].strip() or "Sala",
                                   self.ofields["nome"].strip() or "P1",
                                   password=self.ofields["senha"],
                                   tag=self.ofields["tag"].strip())
            if self.ofields["tag"].strip():
                net.tag_room(self.ofields["tag"].strip(), code)
            self.olobby = {"role": "host", "code": code}
            self._oroom = None
            self.opage = "lobby"
            self.opoll_t = 0
            self.ohb_t = 0
            self.omsg = ""
        except Exception as e:
            self.omsg = str(e)

    def _o_join(self):
        try:
            typed = self.ofields["codigo"].strip()
            code = net.resolve_tag(typed)
            net.request_join(code, self.ofields["nome"].strip() or "P2", self.ofields["senha"])
            if typed.upper() != code:
                try:
                    net.tag_room(typed, code)
                except Exception:
                    pass
            self.olobby = {"role": "guest", "code": code}
            self._oroom = None
            self.opage = "lobby"
            self.opoll_t = 0
            self.ohb_t = 0
            self.omsg = "pedido enviado — esperando o host aprovar"
        except Exception as e:
            self.omsg = str(e)

    def _leave_lobby(self):
        if self.olobby:
            try:
                if self.olobby["role"] == "host":
                    net.close_room(self.olobby["code"])
                else:
                    net.leave_room(self.olobby["code"], "guest")
            except Exception:
                pass
            self.olobby = None

    def _my_name(self):
        return self.ofields["nome"].strip() or "P1"

    def _relay_check_thread(self):
        try:
            from .online import check_relay
            ok, ms, err = check_relay(self.ofields.get("relay", "").strip()
                                      or "ws://localhost:8765")
            self.relay_state = (True, ok, ms, err)
        except Exception as e:
            self.relay_state = (True, False, 0.0, str(e))
        finally:
            self._relay_checking = False

    def _cloud_check_thread(self):
        """Sinal da nuvem: login anônimo + leitura no Firebase (sem relay)."""
        try:
            import time as _t
            t0 = _t.time()
            net.fb_get("rooms/__ping__")
            ms = (_t.time() - t0) * 1000.0
            self.cloud_state = (True, True, ms)
        except Exception as e:
            self.cloud_state = (True, False, 0.0, str(e))
        finally:
            self._cloud_checking = False

    def relay_line(self):
        checked, ok, ms, _err = self.relay_state
        if not checked:
            return "relay: checando…"
        if ok:
            return f"relay OK ({ms:.0f}ms) — pode jogar"
        return "relay FORA DO AR — rode: python relay_server.py"

    def server_line(self):
        """Linha de status do servidor escolhido (nuvem ou relay)."""
        if self.ofields.get("modo") == "nuvem":
            checked, ok, extra = self.cloud_state
            if not checked:
                return T("online.nuvem_check")
            if ok:
                return f"{T('online.nuvem_ok')} ({extra:.0f}ms)" if isinstance(extra, float) else T("online.nuvem_ok")
            return f"{T('online.nuvem_off')} {extra}" if extra else T("online.nuvem_off")
        return self.relay_line()

    def menu_tick(self, dt):
        """No menu: semáforo do servidor + polls do lobby (host aprova sozinho) + heartbeat."""
        if self.section == "online" and self.opage in ("main", "lobby"):
            if self.ofields.get("modo") == "nuvem":
                self._cloud_t -= dt
                if self._cloud_t <= 0 and not self._cloud_checking:
                    self._cloud_t = 6.0
                    self._cloud_checking = True
                    import threading
                    threading.Thread(target=self._cloud_check_thread, daemon=True).start()
            else:
                self._relay_t -= dt
                if self._relay_t <= 0 and not self._relay_checking:
                    self._relay_t = 4.0
                    self._relay_checking = True
                    import threading
                    threading.Thread(target=self._relay_check_thread, daemon=True).start()
        if self.section != "online" or self.opage != "lobby" or not self.olobby:
            return
        role, code = self.olobby["role"], self.olobby["code"]
        self.opoll_t -= dt
        self.ohb_t -= dt
        try:
            if self.opoll_t <= 0:
                self.opoll_t = 2.0
                room = net.get_room(code)
                self._oroom = room
                if room is None:
                    self.omsg = T("online.room_closed")
                    return
                if role == "host":
                    jr = room.get("joinReq")
                    if jr:
                        net.accept_join(code, jr.get("name", "?"))
                        self.omsg = T("online.entered").format(name=jr.get("name", "?"))
                        self._oroom = net.get_room(code)
                else:
                    g = room.get("guest") or {}
                    if g.get("name") == self._my_name() and room.get("status") == "playing":
                        self.omsg = T("online.approved")
            if self.ohb_t <= 0:
                self.ohb_t = 5.0
                net.heartbeat(code, role, self._my_name())
        except Exception as e:
            self.omsg = str(e)

    def _lobby_ready(self):
        room = getattr(self, "_oroom", None)
        if not room or not self.olobby:
            return False
        if self.olobby["role"] == "host":
            g = room.get("guest") or {}
            return bool(g.get("name")) and (net.now_ms() - int(g.get("seen", 0))) < 20000
        g = room.get("guest") or {}
        return g.get("name") == self._my_name() and room.get("status") == "playing"

    def _o_play(self):
        if not self._lobby_ready():
            self.omsg = T("online.waiting")
            return
        nuvem = self.ofields.get("modo") == "nuvem"
        if nuvem:
            checked, ok, _err = self.cloud_state
            if checked and not ok:
                self.omsg = T("online.nuvem_off")
                return
        else:
            checked, ok, _, _ = self.relay_state
            if checked and not ok:
                self.omsg = "liga o relay primeiro: python relay_server.py"
                return
        try:
            room = net.get_room(self.olobby["code"])
            if room is None:
                self.omsg = T("online.room_gone")
                return
            if nuvem:
                # nuvem: sem relay, sem porta, sem processo extra
                from .fbgame import FbSession
                host = self.olobby["role"] == "host"
                sess = FbSession(self.olobby["code"], 0 if host else 1,
                                 self._my_name(), arbiter=host)
                sess.start()
            else:
                self.st.relay = self.ofields["relay"].strip() or "ws://localhost:8765"
                self.st.save()
                from .online import OnlineSession
                sess = OnlineSession(self.st.relay, self.olobby["code"],
                                     self.olobby["role"], self._my_name())
            self.enter_online(sess)
            self.omsg = ""
        except Exception as e:
            self.omsg = str(e)

    # ================= online: partida =================
    def enter_online(self, sess):
        self.online = sess
        self.o_you = sess.you
        self.o_local = self.players[sess.you]
        self.o_foe = self.players[1 - sess.you]
        self.ghost_ok = False
        self.players[0].spawn = pygame.Vector2(C.SPAWN_P1)
        self.players[1].spawn = pygame.Vector2(C.SPAWN_P2)
        for pl in self.players:
            pl.reset()
        self.jets = []
        self.charged = []
        self.sparks = []
        self.floaters = []
        self.balloons = []
        self.score = 0
        self.time = 0.0
        self.winner = ""
        self.winner_sub = ""
        self.shake = 0.0
        self.oacc = 0.0
        self.oseq = 0
        self.oping_t = 0.0
        self.ohb_t = 0.0
        self.ofell_sent = False
        self.cam1.snap_to(self.o_local.p)
        self.cam2.snap_to(self.o_foe.p)
        self.state = "online"
        self.last_mode = "online"

    def leave_online(self):
        if self.online:
            try:
                self.online.close()
            except Exception:
                pass
            self.online = None
        self.o_local = None
        self.o_foe = None
        self._leave_lobby()

    def _update_online(self, dt, intent):
        local, foe = self.o_local, self.o_foe
        self._drive(local, intent, dt)
        if self.online and self.online.alive:
            self.oacc += dt
            if self.oacc >= 1.0 / 20:
                self.oacc = 0.0
                self.oseq += 1
                try:
                    self.online.send_inputs(self.oseq, local)
                except Exception:
                    pass
            self.oping_t -= dt
            if self.oping_t <= 0:
                self.oping_t = 2.0
                try:
                    self.online.ping()
                except Exception:
                    pass
            self.ohb_t -= dt
            if self.ohb_t <= 0 and self.olobby:
                self.ohb_t = 5.0
                try:
                    net.heartbeat(self.olobby["code"], self.olobby["role"], self._my_name())
                except Exception:
                    pass
            for ev in self.online.poll_events():
                self._online_event(ev)
            if self.state != "online" or self.online is None:
                return   # a partida terminou no meio (o outro lado saiu)
            # HP/vidas oficiais (nuvem): o árbitro manda, a previsão some no caminho
            if hasattr(self.online, "hp_of"):
                local.hp = self.online.hp_of(self.o_you)
                local.lives = self.online.lives_of(self.o_you)
        elif self.online is not None:
            # sessão morta (relay caiu, nuvem perdeu o outro lado)
            self.omsg = T("online.closed")
            self.leave_online()
            self.state = "menu"
            self.section = "root"
            return
        # fantasma interpolado
        ghost = self.online.interp_foe() if self.online else None
        if ghost and ghost.get("fresh") and ghost.get("ok"):
            foe.p.update(ghost["x"], ghost["y"])
            foe.v.update(ghost["vx"], ghost["vy"])
            foe.angle = wrap_angle(ghost["a"])
            foe.hp = float(ghost.get("hp", foe.hp))
            foe.lives = int(ghost.get("lives", foe.lives))
            foe.stamina = float(ghost.get("stam", foe.stamina))
            foe.jetting = bool(ghost.get("jet"))
            self.ghost_ok = True
            if foe.jetting and foe.alive and foe.hp > 0:
                self._emit_ghost_jet(dt, foe)
        else:
            self.ghost_ok = False
            foe.jetting = False
        self._online_shots(dt)
        if local.can_act and local.p.y > C.WORLD_H + C.DEATH_MARGIN and not self.ofell_sent:
            self.ofell_sent = True
            try:
                self.online.send_fell()
            except Exception:
                pass
            if hasattr(self.online, "hp_of"):
                # nuvem: respawna na hora, o árbitro só confirma a vida
                local.p = local.spawn.copy()
                local.v = pygame.Vector2(0, 0)
                local.inv = 1.5
                self.ofell_sent = False
                self.floater(local.p.x, local.p.y - 50,
                             T("fight.caiu").format(name=local.name), (255, 120, 120))
        self.cam1.follow(dt, local.p, local.v)
        self.cam2.follow(dt, foe.p, foe.v)
        self.time += dt

    def _emit_ghost_jet(self, dt, foe):
        import random
        tip = foe.tip_pos()
        d = foe.tip_dir()
        foe.jet_acc += C.JET_EMIT_RATE * dt
        perp = pygame.Vector2(-d.y, d.x)
        while foe.jet_acc >= 1.0:
            foe.jet_acc -= 1.0
            speed = C.JET_SPEED * random.uniform(0.9, 1.1)
            self.jets.append(Jet(tip, d * speed + foe.v * C.JET_INHERIT
                                 + perp * random.uniform(-C.JET_SPREAD, C.JET_SPREAD),
                                 foe.idx))

    def _online_event(self, ev):
        from .particles import Spark
        import random
        local, foe = self.o_local, self.o_foe
        t = ev.get("t")
        if t == "dmg":
            if int(ev.get("side", -1)) == self.o_you:
                prev = local.lives
                local.hp = float(ev.get("hp", local.hp))
                local.lives = int(ev.get("lives", local.lives))
                d = local.p - foe.p
                if d.length() < 1:
                    d = pygame.Vector2(0, -1)
                local.v += d.normalize() * 300
                for _ in range(14):
                    self.sparks.append(Spark(local.p, pygame.Vector2(
                        random.uniform(-260, 260), random.uniform(-320, 120)),
                        0.6, random.choice([local.color, C.WHITE, (255, 120, 120)]), 5))
                self.shake = max(self.shake, 8)
                if local.lives < prev:
                    # nuvem: já respawnou na previsão; não teleporta de novo
                    if local.p.y > C.WORLD_H:
                        local.p = local.spawn.copy()
                        local.v = pygame.Vector2(0, 0)
                    local.inv = 1.5
                    self.floater(local.p.x, local.p.y - 50, T("fight.vida"), (255, 120, 120))
            else:
                foe.hp = float(ev.get("hp", foe.hp))
                foe.lives = int(ev.get("lives", foe.lives))
                if ev.get("lost"):
                    local.kills += 1
                    self.floater(foe.p.x, foe.p.y - 50, T("fight.abate"), C.YELLOW)
                self.shake = max(self.shake, 5)
        elif t == "reset":
            if int(ev.get("side", -1)) == self.o_you:
                local.hp = float(ev.get("hp", C.HP_MAX))
                local.lives = int(ev.get("lives", local.lives))
                # se já respawnou na previsão, não teleporta de novo
                if local.p.y > C.WORLD_H:
                    local.p = local.spawn.copy()
                    local.v = pygame.Vector2(0, 0)
                local.inv = 1.5
                self.ofell_sent = False
        elif t == "pred":
            # aviso rápido de dano (nuvem): a confirmação oficial vem depois
            side = int(ev.get("side", -1))
            if side == self.o_you:
                self.shake = max(self.shake, 6)
                for _ in range(8):
                    self.sparks.append(Spark(local.p, pygame.Vector2(
                        random.uniform(-220, 220), random.uniform(-280, 100)),
                        0.5, random.choice([local.color, C.WHITE, (255, 120, 120)]), 4))
        elif t == "closed":
            self.omsg = T("online.closed")
            self.leave_online()
            self.state = "menu"
            self.section = "root"
        elif t == "over":
            w = int(ev.get("winner", 1 - self.o_you))
            self.winner = T("over.win").format(
                name="VOCÊ" if w == self.o_you else self.players[w].name)
            self.winner_sub = T("over.sub_online").format(
                code=self.olobby["code"] if self.olobby else "?", time=f"{self.time:.1f}")
            self.state = "over"

    def _online_shots(self, dt):
        """Física dos projéteis; dano SÓ via relay (claims)."""
        local, foe = self.o_local, self.o_foe
        for j in list(self.jets):
            if not j.update(dt):
                self.jets.remove(j)
                continue
            if (j.owner == local.idx and self.ghost_ok and foe.alive and foe.hp > 0
                    and (j.p - foe.p).length() < C.PLAYER_R + j.size):
                try:
                    self.online.send_hit(C.CHIP_DMG, False, j.p.x, j.p.y)
                except Exception:
                    pass
                if j in self.jets:
                    self.jets.remove(j)
        for cb in list(self.charged):
            alive_ball = cb.update(dt)
            hit = (cb.owner == local.idx and self.ghost_ok and foe.alive and foe.hp > 0
                   and (cb.p - foe.p).length() < C.PLAYER_R + cb.size)
            if hit:
                try:
                    self.online.send_hit(cb.dmg, True, cb.p.x, cb.p.y)
                except Exception:
                    pass
            if hit or not alive_ball:
                if cb in self.charged:
                    self.charged.remove(cb)
                self._explode(cb.p, cb.size * 1.5)

    def set_viewport(self, size):
        self.view_size = size
        if self.controls.page == "layout":
            self.controls.viewport = size
        w, h = size
        self.cam_full.resize(w, h)
        self.cam1.resize(w if self.state == "online" else w/2, h)
        self.cam2.resize(w/2, h)

    def view_of(self, idx):
        """(câmera, origem x da viewport no canvas) do jogador."""
        both = self.state in ("versus", "online")
        if both and idx == 1:
            return self.cam2, self.view_size[0]/2
        if both:
            return self.cam1, 0
        return self.cam_full, 0

    def to_world(self, canvas_pos, idx=0):
        """Mouse do canvas -> mundo (a mira precisa disso com a câmera rolando)."""
        cam, vx = self.view_of(idx)
        return (canvas_pos[0] - vx + cam.x, canvas_pos[1] + cam.y)

    # ================= update =================
    def update(self, dt, intent1, intent2=None):
        if self.state == "online":
            self._update_online(dt, intent1)
        elif self.state == "treino":
            if self.tmode == "labirinto":
                self._update_labirinto(dt, intent1)
            elif self.tmode == "bots":
                self._update_bots(dt, intent1)
            else:
                p = self.players[0]
                self._drive(p, intent1, dt)
                self.time += dt
                for bl in self.balloons:
                    bl.update(dt, near=p.p)
                self._shots_vs_balloons()
                self._check_fall(p)
                if p.down:
                    p.update_physics(dt, self.sparks)
                    p.respawn_if_ready()
                self.cam_full.follow(dt, p.p, p.v)
                if not p.alive:
                    self.winner = T("over.gameover")
                    self.winner_sub = T("over.sub_treino").format(
                        score=self.score, combo=self.max_combo, time=f"{self.time:.1f}")
                    self.state = "over"
        elif self.state == "versus":
            self._drive(self.players[0], intent1, dt)
            self._drive(self.players[1], intent2, dt)
            self._separate_players()
            self.time += dt
            for pl in self.players:
                self._check_fall(pl)
                if pl.down:
                    pl.update_physics(dt, self.sparks)
                    pl.respawn_if_ready()
            self.cam1.follow(dt, self.players[0].p, self.players[0].v)
            self.cam2.follow(dt, self.players[1].p, self.players[1].v)
            out = [pl for pl in self.players if not pl.alive]
            if out:
                if len(out) == 2:
                    self.winner = T("over.draw")
                    self.winner_sub = T("over.sub_draw")
                else:
                    w = self.players[1] if out[0] is self.players[0] else self.players[0]
                    self.winner = T("over.win").format(name=w.name)
                    self.winner_sub = T("over.sub_win").format(
                        kills=w.kills, time=f"{self.time:.1f}")
                self.state = "over"
        else:
            return

        if self.state in ("treino", "versus"):
            self._shots_vs_players(dt)
        # score animado conta até o real; combo pulsa
        if self.disp_score < self.score:
            self.disp_score = min(self.score, self.disp_score + max(1, self.score - self.disp_score) * dt * 8)
        else:
            self.disp_score = self.score
        self.combo_pop = max(0.0, self.combo_pop - dt * 3.0)
        for s in list(self.sparks):
            if not s.update(dt):
                self.sparks.remove(s)
        for f in list(self.floaters):
            f["life"] -= dt
            f["p"].y -= 45 * dt
            if f["life"] <= 0:
                self.floaters.remove(f)
        self.shake = max(0.0, self.shake - dt * 30)

    def _update_labirinto(self, dt, intent):
        p = self.players[0]
        self._drive(p, intent, dt)
        self.time += dt
        self.mtime += dt
        mz = self.tmaze
        mz.update(dt)
        if p.can_act:
            mz.collide(p.p, C.PLAYER_R, p.v)
            # checkpoints em ordem
            if self.mcp < len(mz.checkpoints) - 1:
                nxt = mz.checkpoints[self.mcp + 1]
                if (p.p - nxt).length() < 46:
                    self.mcp += 1
                    self.floater(nxt.x, nxt.y - 30, T("modos.maze_check"), (120, 255, 170))
            # orbes mandam de volta (checkpoint ou começo, pela dificuldade)
            for o in mz.orbs:
                if (p.p - o.p).length() < C.PLAYER_R + o.r and p.inv <= 0:
                    cfg = C.MAZE_DIFFS[self.mdiff]
                    back = mz.start if cfg["fallback"] == "start" else mz.checkpoints[self.mcp]
                    p.p = back.copy()
                    p.v *= 0
                    p.inv = 1.0
                    self.mtime += cfg["penalty"]
                    self.floater(back.x, back.y - 40,
                                 T("modos.maze_penalty").format(t=cfg["penalty"]),
                                 (255, 120, 120))
                    break
            # bandeira = próximo nível (labirinto novo, zera o relógio da fase)
            if (p.p - mz.goal).length() < 52:
                self.mtotal += self.mtime
                self.floater(mz.goal.x, mz.goal.y - 40, T("modos.maze_goal"), C.YELLOW)
                from .maze import Maze
                self.tmaze = Maze(self.mdiff)
                p.p = self.tmaze.start.copy()
                p.v *= 0
                p.inv = 1.0
                self.mlevel += 1
                self.mtime = 0.0
                self.mcp = 0
        if p.down:
            p.update_physics(dt, self.sparks)
            p.respawn_if_ready()
        self.cam_full.follow(dt, p.p, p.v)

    def _update_bots(self, dt, intent1):
        p = self.players[0]
        self._drive(p, intent1, dt)
        foes = self.fighters()
        for bot, brain in zip(self.tbots, self.brains):
            if bot.can_act or bot.down:
                self._drive(bot, brain.decide(bot, foes, dt), dt)
        self._separate_fighters()
        self.time += dt
        for f in foes:
            self._check_fall(f)
            if f.down:
                f.update_physics(dt, self.sparks)
                f.respawn_if_ready()
        self.cam_full.follow(dt, p.p, p.v)
        if not p.alive:
            place = 1 + sum(1 for b in self.tbots if b.alive)
            self.winner = T("over.gameover")
            self.winner_sub = T("modos.place").format(n=place)
            self.state = "over"
        elif self.tbots and not any(b.alive for b in self.tbots):
            self.winner = T("over.win").format(name=p.name)
            self.winner_sub = T("over.sub_win").format(kills=p.kills, time=f"{self.time:.1f}")
            self.state = "over"

    def _check_fall(self, pl):
        if pl.can_act and pl.p.y > C.WORLD_H + C.DEATH_MARGIN:
            pl.fell_out(self.sparks)
            self.floater(pl.p.x, C.WORLD_H - 60, T("fight.caiu").format(name=pl.name),
                         (255, 120, 120))
            if self.state == "treino":
                self.combo = 0

    def _drive(self, pl, intent, dt):
        if intent is None:
            pl._flap_held = False
            if pl.can_act or pl.down:
                pl.update_physics(dt, self.sparks)
            return
        if intent.use_mouse:
            pl.aim_at(intent.mouse_pos, dt)
        if intent.rotate:
            pl.rotate_keyboard(intent.rotate, dt)
        pl.stabilizing = bool(intent.action) and pl.can_act
        # edge: segurar o botão NÃO pula — cada pulo é um aperto
        if intent.flap and not pl._flap_held:
            pl.flap(self.sparks)
        pl._flap_held = bool(intent.flap)
        fired = pl.update_jet(dt, intent.jet, intent.action,
                              self.jets, self.charged, self.sparks)
        if fired is not None:
            self.shake = max(self.shake, 10)
            self.floater(pl.p.x, pl.p.y - 50, T("fight.bolona"), C.YELLOW)
        if pl.can_act or pl.down:
            pl.update_physics(dt, self.sparks)

    def _shots_vs_balloons(self):
        p = self.players[0]
        for shot in list(self.jets) + list(self.charged):
            big = shot in self.charged
            for bl in self.balloons:
                if (shot.p - bl.p).length() < bl.r + shot.size + (10 if big else 0):
                    self.combo += 1
                    self.combo_pop = 1.0
                    self.max_combo = max(self.max_combo, self.combo)
                    gained = 100 + 10 * min(self.combo, 50)
                    self.score += gained
                    self.floater(bl.p.x, bl.p.y, f"+{gained}", C.WHITE, self.font)
                    if self.combo >= 5:
                        self.floater(bl.p.x, bl.p.y - 26, T("hud.combo").format(n=self.combo),
                                     C.YELLOW, self.f_sm)
                    self.shake = max(self.shake, 4)
                    for _ in range(12):
                        self.sparks.append(Spark(bl.p, pygame.Vector2(
                            random.uniform(-240, 240), random.uniform(-300, 60)),
                            0.5, bl.color, 5))
                    bl.reset(near=p.p)
                    self._remove_shot(shot)
                    break

    def _remove_shot(self, shot):
        if shot in self.jets:
            self.jets.remove(shot)
        elif shot in self.charged:
            self.charged.remove(shot)
            self._explode(shot.p, shot.size)

    def _explode(self, pos, size):
        for _ in range(int(10 + size)):
            self.sparks.append(Spark(pos, pygame.Vector2(random.uniform(-320, 320),
                                                         random.uniform(-380, 80)),
                                     0.7, random.choice([(255, 255, 255), (170, 210, 255),
                                                         (255, 200, 120)]), 6))

    def _shots_vs_players(self, dt):
        for j in list(self.jets):
            if not j.update(dt):
                self.jets.remove(j)
                continue
            for pl in self.active_players():
                if not pl.can_act:
                    continue
                if j.owner == pl.idx and j.age < C.SELF_JET_GRACE:
                    continue
                if (j.p - pl.p).length() < C.PLAYER_R + j.size:
                    lost = pl.take_hit(C.CHIP_DMG, False, j.p, j.v, self.sparks)
                    self.shake = max(self.shake, 5)
                    if j in self.jets:
                        self.jets.remove(j)
                    self._on_life_lost(pl, j.owner, lost)
                    break
        for cb in list(self.charged):
            alive_ball = cb.update(dt)
            hit_someone = False
            for pl in self.active_players():
                if not pl.can_act or cb.owner == pl.idx:
                    continue
                if (cb.p - pl.p).length() < C.PLAYER_R + cb.size:
                    lost = pl.take_hit(cb.dmg, True, cb.p, cb.v, self.sparks)
                    self.shake = max(self.shake, 11)
                    self._on_life_lost(pl, cb.owner, lost)
                    hit_someone = True
                    break
            if hit_someone or not alive_ball:
                if cb in self.charged:
                    self.charged.remove(cb)
                self._explode(cb.p, cb.size * 1.5)

    def _on_life_lost(self, victim, attacker_idx, lost):
        if not lost:
            return
        if self.state == "treino" and self.tmode != "bots":
            self.combo = 0
            self.floater(victim.p.x, victim.p.y - 50, T("fight.vida"), (255, 120, 120))
        else:
            self._credit(attacker_idx)
            self.floater(victim.p.x, victim.p.y - 50,
                         T("fight.perdeu").format(name=victim.name), (255, 120, 120))

    def _separate_fighters(self):
        fs = [f for f in self.fighters() if f.can_act]
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                a, b = fs[i], fs[j]
                d = b.p - a.p
                dist = d.length()
                min_d = C.PLAYER_R * 2
                if 0 < dist < min_d:
                    n = d / dist
                    push = (min_d - dist) / 2
                    a.p -= n * push
                    b.p += n * push

    def _separate_players(self):
        self._separate_fighters()

    # ================= desenho =================
    def txt(self, s, text, f, c, x, y):
        if isinstance(s, ViewSurface):
            size, bold = _font_meta.get(f, (f.get_height(), False))
            native_font = get_font(max(6, round(size*s.scale)), bold)
            img = rendered_text(native_font, text, tuple(c))
            s.surface.blit(img, img.get_rect(center=s.point((x, y))))
            return
        img = rendered_text(f, text, tuple(c))
        s.blit(img, img.get_rect(center=(x, y)))

    def txt_fit(self, s, text, max_w, size, c, x, y, bold=False):
        f = fit_font(text, max_w, size, bold)
        self.txt(s, text, f, c, x, y)

    def draw_diagnostics(self, surface, stats, source):
        if self.state == "menu" or (not self.st.show_fps and not self.st.debug_stats):
            return
        if not isinstance(surface, ViewSurface):
            surface = ViewSurface(surface, Geometry(surface.get_size()), ui=True, smooth=self.st.smooth_scaling)
        surface = surface.hud(self.st.hud_scale)
        panel = pygame.Rect(surface.get_width()/2-124, 6, 248,
                            60 if self.st.debug_stats and self.st.show_fps else 29)
        draw.rect(surface, (15, 22, 35), panel, border_radius=7)
        if self.st.show_fps:
            self.txt_fit(surface, T("extras.fps_line").format(fps=f"{stats.fps:.0f}"), 230,
                         18, C.CYAN, panel.centerx, panel.y+14)
        if self.st.debug_stats:
            line = T("extras.stats_line").format(ms=f"{stats.ms:.1f}", device=source,
                                                n=len(self.jets)+len(self.charged))
            self.txt_fit(surface, line, 230, 14, C.WHITE, panel.centerx, panel.bottom-16)

    def _draw_world(self, s, cam, vx, vy, vw, vh, mode, shake=(0, 0),
                    viewer=None, others=()):
        s.set_clip(pygame.Rect(vx, vy, vw, vh))
        s.fill(C.BG, (vx, vy, vw, vh))
        ox = cam.x - vx + shake[0]  # offset mundo->tela dentro da viewport
        oy = cam.y - vy + shake[1]
        off = (ox, oy)
        # Em qualidade baixa, desabilita pontos do fundo (reduz draw significativamente)
        show_bg = self.st.bg and not (self.st.quality == "low")
        if show_bg:
            self._bg_dots_view(s, cam, vx, vy, vw, vh)
        # limite do mundo (brilho onde acaba o mapa)
        bx0, by0 = -ox, -oy
        bx1, by1 = C.WORLD_W - ox, C.WORLD_H - oy
        if bx0 < vx + vw and bx1 > vx and by0 < vy + vh and by1 > vy:
            draw.rect(s, (70, 90, 140), (bx0, by0, C.WORLD_W, C.WORLD_H), 3)
        if mode == "treino":
            if self.tmode == "labirinto" and self.tmaze is not None:
                self.tmaze.draw(s, off, self.mcp)
            else:
                for bl in self.balloons:
                    bl.draw(s, off)
        for j in self.jets:
            j.draw(s, off)
        for cb in self.charged:
            cb.draw(s, off)
        if self.st.particles:
            # Em qualidade baixa, corta partículas pela metade (culling + stride)
            stride = max(1, round(1/self.st.particle_density))
            if self.st.quality == "low":
                stride = max(2, stride * 2)
            for sp in self.sparks[::stride]:
                sp.draw(s, off)
        for pl in self.active_players():
            if self.state == "online" and pl is self.o_foe and not self.ghost_ok:
                continue  # sem sinal do oponente: não desenha o fantasma
            pl.draw(s, off, show_stamina=self.st.show_stamina)
        for f in self.floaters:
            a = max(0.0, f["life"] / f["max"])
            if a <= 0:
                continue
            img = f["font"].render(f["text"], True, f["color"])
            img.set_alpha(int(255 * a))
            s.blit(img, img.get_rect(center=(int(f["p"][0] - ox), int(f["p"][1] - oy))))
        if viewer is not None and self.st.show_arrows:
            self._draw_arrows(s, cam, vx, vy, vw, vh, viewer, others)
        s.set_clip(None)

    def _draw_arrows(self, s, cam, vx, vy, vw, vh, viewer, others):
        """Setas na borda p/ quem tá fora da tela (sabe onde tá o outro)."""
        cx, cy = vx + vw / 2, vy + vh / 2
        m = C.ARROW_MARGIN
        for pl, ok in others:
            if pl is viewer or not pl.alive:
                continue
            sx, sy = pl.p.x - cam.x + vx, pl.p.y - cam.y + vy
            if vx + m < sx < vx + vw - m and vy + m < sy < vy + vh - m:
                continue
            ang = math.atan2(sy - cy, sx - cx)
            dx, dy = math.cos(ang), math.sin(ang)
            tx = (vw / 2 - m) / abs(dx) if abs(dx) > 1e-6 else 1e9
            ty = (vh / 2 - m) / abs(dy) if abs(dy) > 1e-6 else 1e9
            t = min(tx, ty)
            px, py = cx + dx * t, cy + dy * t
            col = pl.color if ok else (110, 115, 135)
            sz = C.ARROW_SIZE
            tip = (px + dx * sz, py + dy * sz)
            l = (px - dy * sz * 0.6 - dx * sz * 0.4, py + dx * sz * 0.6 - dy * sz * 0.4)
            r = (px + dy * sz * 0.6 - dx * sz * 0.4, py - dx * sz * 0.6 - dy * sz * 0.4)
            draw.polygon(s, col, [tip, l, r])
            dist = int(math.hypot(pl.p.x - viewer.p.x, pl.p.y - viewer.p.y) / 50)
            img = self.f_sm.render(f"{pl.name} {dist}m", True, col)
            s.blit(img, img.get_rect(center=(int(px), int(py + sz + 10))))

    def _bg_dots_view(self, s, cam, vx, vy, vw, vh):
        if not self.st.bg:
            return
        cell = 170
        for i in range(int(cam.x // cell) - 1, int((cam.x + vw) // cell) + 2):
            for j in range(int(cam.y // cell) - 1, int((cam.y + vh) // cell) + 2):
                h = (i * 73856093) ^ (j * 19349663)
                if h % 100 < 30*self.st.bg_density:
                    dx = (abs(h) // 7) % (cell - 20) + 10
                    dy = (abs(h) // 13) % (cell - 20) + 10
                    draw.circle(s, (30, 34, 55),
                                       (int(vx + i * cell + dx - cam.x),
                                        int(vy + j * cell + dy - cam.y)), 2)

    def draw(self, screen):
        geometry = Geometry(screen.get_size())
        self.set_viewport(geometry.world_size)
        ui = ViewSurface(screen, geometry, ui=True, smooth=self.st.smooth_scaling)
        screen = ViewSurface(screen, geometry, smooth=self.st.smooth_scaling)
        vw, vh = self.view_size
        if self.state == "menu":
            self.draw_menu(ui)
            return
        mode = self.state if self.state in ("treino", "versus") else self.last_mode
        if self.state == "online":
            mode = "versus"  # mesmo palco split, sem balões
        shake = self.shake*self.st.shake_strength if self.st.shake else 0
        sh = (random.uniform(-shake, shake), random.uniform(-shake, shake)) if shake > 0 else (0, 0)
        screen.fill((0, 0, 0))
        if mode == "treino":
            me = self.players[0]
            others = [(b, True) for b in self.tbots] if self.tmode == "bots" else []
            self._draw_world(screen, self.cam_full, 0, 0, vw, vh, mode, sh,
                             viewer=me, others=others)
        elif self.state == "online":
            # sem split: tela cheia na sua câmera + seta p/ o oponente
            me, foe = self.o_local, self.o_foe
            others = [(foe, self.ghost_ok)] if foe is not None else []
            self._draw_world(screen, self.cam1, 0, 0, vw, vh, mode, sh,
                             viewer=me, others=others)
        else:
            hw = vw/2
            a, b = self.players
            self._draw_world(screen, self.cam1, 0, 0, hw, vh, mode, sh,
                             viewer=a, others=[(b, True)])
            self._draw_world(screen, self.cam2, hw, 0, vw-hw, vh, mode, sh,
                             viewer=b, others=[(a, True)])
            draw.line(screen, (60, 70, 100), (hw, 0), (hw, vh), 2)
        screen = ui
        self.draw_hud(ui.hud(self.st.hud_scale), mode)
        if self.state in ("treino", "versus", "online"):
            self.draw_touch(screen)
        if self.state == "over":
            screen = ui.reference()
            draw.rect(screen, (10, 12, 22), (0, C.H // 2 - 78, C.W, 156))
            self.txt_fit(screen, self.winner, C.W - 80, 44, C.YELLOW, C.W // 2, C.H // 2 - 22, True)
            self.txt_fit(screen, self.winner_sub, C.W - 80, 20, C.WHITE, C.W // 2, C.H // 2 + 16)
            self.txt(screen, T("over.hint"),
                     self.font, (150, 160, 190), C.W // 2, C.H // 2 + 50)

    # ---------- HUD limpo (sem rodinha fixa; bolinha some/esvanece no mundo) ----------
    def draw_card(self, s, pl, right=False):
        W_, H_ = 272, 62
        x = s.get_width() - 10 - W_ if right else 10
        y = 8
        card = pygame.Surface((W_, H_), pygame.SRCALPHA)
        card.fill((18, 22, 40, 190))
        draw.rect(card, (*pl.color, 230), (0, 0, W_, H_), 2, border_radius=12)
        s.blit(card, (x, y))
        ax = (x + 26) if not right else (x + W_ - 26)
        draw.circle(s, pl.color, (ax, y + 24), 13)
        self.txt(s, pl.name, self.f_sm, (10, 12, 24), ax, y + 24)
        bx = x + 46 if not right else x + 12
        bw, bh = 200, 13
        by = y + 12
        draw.rect(s, (12, 14, 26), (bx, by, bw, bh), border_radius=7)
        pct = max(0.0, pl.disp_hp / C.HP_MAX)  # fantasma branco animado...
        if pct > 0:
            draw.rect(s, (220, 225, 235), (bx, by, int(bw * pct), bh), border_radius=7)
        pct = max(0.0, pl.hp / C.HP_MAX)       # ...e o HP real por cima
        if pct > 0:
            draw.rect(s, hp_color(pct), (bx, by, int(bw * pct), bh), border_radius=7)
        for i in range(C.LIVES_START):
            cx = bx + 8 + i * 20
            c = (255, 110, 120) if i < pl.lives else (55, 60, 80)
            draw.circle(s, c, (cx, by + 26), 6)
        if pl.exhausted:
            self.txt_fit(s, T("hud.exhausted").format(s=f"{pl.exhaust_t:.0f}"), 120, 15,
                         (255, 120, 120), bx + 150, by + 26)
        elif pl.charge_ready:
            blink = (pygame.time.get_ticks() // 350) % 2 == 0
            self.txt_fit(s, T("hud.charge"), 120, 15, C.YELLOW if blink else (170, 160, 110),
                         bx + 150, by + 26)

    def draw_mini_card(self, s, pl, i):
        """Cartão compacto pros bots (canto direito, empilhados)."""
        W_, H_ = 190, 40
        x, y = s.get_width() - 10 - W_, 78 + i * (H_ + 6)
        card = pygame.Surface((W_, H_), pygame.SRCALPHA)
        card.fill((18, 22, 40, 170))
        draw.rect(card, (*pl.color, 200), (0, 0, W_, H_), 1, border_radius=9)
        s.blit(card, (x, y))
        draw.circle(s, pl.color, (x + 16, y + 20), 9)
        self.txt_fit(s, pl.name, 110, 15, C.WHITE, x + 78, y + 11)
        bw = 150
        pct = max(0.0, pl.hp / C.HP_MAX)
        draw.rect(s, (12, 14, 26), (x + 30, y + 22, bw, 9), border_radius=5)
        if pct > 0:
            draw.rect(s, hp_color(pct), (x + 30, y + 22, int(bw * pct), 9),
                             border_radius=5)
        for k in range(C.LIVES_START):
            c = (255, 110, 120) if k < pl.lives else (55, 60, 80)
            draw.circle(s, c, (x + W_ - 16 - k * 16, y + 11), 5)

    def draw_touch(self, s):
        """Layout persistido, visível antes mesmo do primeiro toque no mobile."""
        from . import input as inp
        if not self.touch_visible and not inp.touch_active():
            return
        draw_touch(s, self, self.st.controls["touch_layout"])

    def draw_hud(self, s, mode):
        sw, sh = s.get_size()
        if mode == "treino" and self.tmode == "labirinto":
            self.draw_card(s, self.players[0])
            self.txt(s, T("modos.maze_level").format(n=self.mlevel),
                     self.f_score, C.YELLOW, sw/2, 110)
            if self.st.show_timer:
                self.txt(s, T("modos.maze_time").format(t=f"{self.mtime:.1f}"),
                         self.font, C.WHITE, sw/2, 142)
            if self.tmaze is not None:
                self.txt(s, T("modos.maze_cp").format(i=min(self.mcp + 1, len(self.tmaze.checkpoints) - 1),
                                                      k=len(self.tmaze.checkpoints) - 1),
                         self.f_sm, (130, 140, 170), sw/2, 164)
            if self.st.show_hints:
                self.txt_fit(s, T("modos.maze_hint"), sw-40, 15, (140, 150, 180), sw/2, sh-12)
        elif mode == "treino" and self.tmode == "bots":
            self.draw_card(s, self.players[0])
            if self.st.show_bot_hud:
                for i, b in enumerate(self.tbots):
                    self.draw_mini_card(s, b, i)
            if self.st.show_timer:
                self.txt(s, f"{self.time:.0f}s", self.font, C.WHITE, sw/2, 84)
            if self.st.show_hints:
                self.txt_fit(s, T("modos.bots_hint"), sw-40, 15, (140, 150, 180), sw/2, sh-12)
        elif mode == "treino":
            self.draw_card(s, self.players[0])
            if self.st.show_timer:
                self.txt(s, f"{self.time:.0f}s", self.font, C.WHITE, sw/2, 84)
            img = self.f_score.render(f"{int(self.disp_score):07d}", True, C.WHITE)
            s.blit(img, img.get_rect(topright=(sw-14, 84)))
            self.txt(s, T("hud.max_combo").format(n=self.max_combo), self.f_sm,
                     (130, 140, 170), sw-58, 126)
            if self.combo >= 2:
                pop = 1.0 + 0.5 * self.combo_pop
                img = self.f_combo.render(f"{self.combo}x", True, (150, 160, 200))
                img.set_alpha(150)
                w, h = img.get_size()
                img = pygame.transform.smoothscale(img, (int(w * pop), int(h * pop)))
                s.blit(img, img.get_rect(bottomleft=(22, sh-34)))
            if self.st.show_hints:
                self.txt_fit(s, T("hud.treino_hint"), sw-40, 15, (140, 150, 180), sw/2, sh-12)
        else:
            self.draw_card(s, self.players[0])
            self.draw_card(s, self.players[1], right=True)
            a, b = self.players
            timer = f"   •   {self.time:.0f}s" if self.st.show_timer else ""
            self.txt(s, f"{a.kills} : {b.kills}"+timer, self.font, C.WHITE, sw/2, 84)
            if self.state == "online" and self.online:
                code = self.olobby["code"] if self.olobby else "?"
                ping = f"{int(self.online.rtt * 1000)}ms"
                sb = T("hud.no_signal") if not self.ghost_ok else ""
                self.txt_fit(s, T("hud.online_line").format(code=code, ping=ping, extra=sb),
                             400, 16, C.YELLOW if self.ghost_ok else (255, 120, 120),
                             sw/2, 110)
            if self.st.show_hints:
                self.txt_fit(s, T("hud.versus_hint"), sw-40, 15, (140, 150, 180), sw/2, sh-12)
        if self.st.show_minimap:
            self.draw_minimap(s)

    def draw_minimap(self, s):
        mw, mh = C.MINIMAP_SIZE
        x, y = (s.get_width()-mw)/2, s.get_height()-mh-44
        draw.rect(s, (22, 28, 45), (x, y, mw, mh), border_radius=6)
        draw.rect(s, (100, 120, 160), (x, y, mw, mh), 1, border_radius=6)
        for pl in self.active_players():
            if pl.can_act:
                px = x+max(0, min(1, pl.p.x/C.WORLD_W))*mw
                py = y+max(0, min(1, pl.p.y/C.WORLD_H))*mh
                draw.circle(s, pl.color, (px, py), 4)

    # ---------- treino: submenu ----------
    def draw_treino(self, s):
        pw, ph = 600, 380
        px, py = C.W // 2 - pw // 2, 130
        draw.rect(s, (18, 22, 40), (px, py, pw, ph), border_radius=16)
        draw.rect(s, (90, 200, 150), (px, py, pw, ph), 2, border_radius=16)
        self.txt(s, T("modos.t_menu"), self.font, C.WHITE, C.W // 2, py + 26)
        self.trow_rects = []
        if self.tpage == "mode":
            names = {"baloes": ("modos.m_baloes", "modos.d_baloes"),
                     "labirinto": ("modos.m_lab", "modos.d_lab"),
                     "bots": ("modos.m_bots", "modos.d_bots")}
            rows = [(m, T(names[m][0]), T(names[m][1])) for m in self.TMODES]
            rows.append(("back", T("modos.m_voltar"), T("modos.hint_mode")))
            for i, (kind, name, desc) in enumerate(rows):
                ry = py + 66 + i * 72
                sel = (i == self.tfocus)
                rect = pygame.Rect(px + 24, ry - 4, pw - 48, 62)
                if sel:
                    draw.rect(s, (50, 90, 190), rect, border_radius=10)
                draw.rect(s, C.YELLOW if sel else (90, 100, 140), rect, 2,
                                 border_radius=10)
                self.txt(s, name, self.font, C.WHITE, C.W // 2, ry + 12)
                self.txt_fit(s, desc, pw - 100, 15, (150, 160, 190), C.W // 2, ry + 38)
                self.trow_rects.append(("mode", i, rect))
        else:
            items = self._topt_items()
            for i, (kind, label) in enumerate(items):
                ry = py + 66 + i * 62
                sel = (i == self.tfocus)
                rect = pygame.Rect(px + 24, ry - 4, pw - 48, 50)
                if kind == "go":
                    if sel:
                        draw.rect(s, (50, 150, 90), rect, border_radius=10)
                    draw.rect(s, C.YELLOW if sel else (90, 100, 140), rect, 2,
                                     border_radius=10)
                    self.txt(s, label, self.f_score, C.WHITE, C.W // 2, ry + 20)
                else:
                    if sel:
                        draw.rect(s, (50, 90, 190), rect, border_radius=10)
                    draw.rect(s, C.YELLOW if sel else (90, 100, 140), rect, 1,
                                     border_radius=10)
                    self.txt_fit(s, label, pw - 100, 20, C.WHITE, C.W // 2, ry + 20)
                self.trow_rects.append(("opt" if kind != "back" else "back", i, rect))
            self.txt(s, T("modos.hint_opt"), self.f_sm, (150, 160, 190),
                     C.W // 2, py + ph - 22)

    # ---------- menu XMB ----------
    def draw_icon(self, s, kind, rect, color, selected):
        x, y, w, h = rect
        if selected:
            draw.rect(s, color, (x - 6, y - 6, w + 12, h + 12), 2, border_radius=18)
        draw.rect(s, (30, 36, 60), rect, border_radius=14)
        draw.rect(s, color, rect, 3, border_radius=14)
        cx, cy = x + w // 2, y + h // 2
        if kind == "treino":
            for r, c in ((22, color), (14, (30, 36, 60)), (7, (255, 255, 255))):
                draw.circle(s, c, (cx, cy), r)
        elif kind == "versus":
            draw.circle(s, C.CYAN, (cx - 10, cy), 14)
            draw.circle(s, C.ORANGE, (cx + 10, cy), 14)
        elif kind == "online":
            draw.circle(s, color, (cx, cy), 20, 3)
            draw.ellipse(s, color, (cx - 20, cy - 9, 40, 18), 2)
            draw.line(s, color, (cx, cy - 20), (cx, cy + 20), 2)
        elif kind == "settings":
            for i in range(3):
                yy = cy - 14 + i * 14
                draw.line(s, (120, 130, 160), (cx - 20, yy), (cx + 20, yy), 3)
                draw.circle(s, color, (cx - 20 + ((i * 17 + 8) % 40), yy), 6)
        elif kind == "sair":
            draw.arc(s, color, (cx - 16, cy - 16, 32, 32), -0.6, math.pi * 2 + 0.6 - math.pi, 4)
            draw.line(s, color, (cx, cy - 20), (cx, cy + 4), 4)

    def draw_menu(self, s):
        if self.section == "settings":
            editor = self.settings_menu.name == "controls" and self.controls.page == "layout"
            self.settings_menu.draw(s if editor else s.reference())
            return
        if self.section == "controls":
            self.controls.draw(s.reference(), self)
            return
        s.fill(C.BG)
        sw, sh = s.get_size()
        for i in range(5):
            draw.circle(s, (26, 30, 52), (sw-120, 120), 60+i*45, 2)
        self.txt(s, T("menu.title"), self.big, C.YELLOW, 90, 52)
        self.txt(s, T("menu.subtitle"), self.font, C.WHITE, 132, 92)
        self.menu_rects = []
        kinds = root_kinds()
        n = len(kinds)
        size_sel, size = 124, 96
        gap = (sw-180)/max(1, n-1)
        total = (n - 1) * gap
        y0 = sh*.46
        for i, kind in enumerate(kinds):
            sel = (i == self.mi and self.section == "root")
            sz = size_sel if sel else size
            x = sw/2-total/2+i*gap-sz/2
            y = y0 - sz // 2
            rect = pygame.Rect(x, y, sz, sz)
            self.menu_rects.append(rect)
            col = MENU_COLORS[kind]
            self.draw_icon(s, kind, rect, col, sel)
            self.txt_fit(s, T("menu." + kind), 150, 34 if sel else 20, C.WHITE if sel else (170, 180, 205),
                         x + sz // 2, y + sz + 28, sel)
        self.txt_fit(s, T("menu.desc_"+kinds[self.mi % n]), sw-100, 20, (150, 160, 190), sw/2, sh*.78)
        panel = s.reference()
        if self.section == "online":
            self.draw_online(panel)
        elif self.section == "treino":
            self.draw_treino(panel)
        elif self.section == "gfx":
            pw, ph = 560, 320
            px, py = C.W // 2 - pw // 2, 130
            draw.rect(s, (18, 22, 40), (px, py, pw, ph), border_radius=16)
            draw.rect(s, (90, 120, 220), (px, py, pw, ph), 2, border_radius=16)
            self.txt(s, T("menu.gfx_title"), self.font, C.WHITE, C.W // 2, py + 26)
            self.gfx_rects = []
            for i, key in enumerate(GFX_ROWS):
                ry = py + 58 + i * 40
                sel = (i == self.gi)
                if sel:
                    draw.rect(s, (50, 90, 190), (px + 16, ry - 4, pw - 32, 34),
                                     border_radius=9)
                self.txt(s, T(key), self.font, C.WHITE, px + 130, ry + 12)
                self.txt_fit(s, self.gfx_value(i), 220, 20,
                             C.YELLOW if sel else (170, 180, 205), px + pw - 130, ry + 12)
                self.gfx_rects.append(pygame.Rect(px + 16, ry - 4, pw - 32, 34))
            self.txt(s, T("menu.gfx_footer"), self.f_sm,
                     (150, 160, 190), C.W // 2, py + ph - 18)
        else:
            self.txt_fit(s, T("menu.footer"), sw-40, 18, (150, 160, 190), sw/2, sh-30)

    # ---------- online: telas ----------
    def draw_online(self, s):
        pw, ph = 620, 400
        px, py = C.W // 2 - pw // 2, 120
        draw.rect(s, (18, 22, 40), (px, py, pw, ph), border_radius=16)
        draw.rect(s, (90, 200, 150), (px, py, pw, ph), 2, border_radius=16)
        titles = {"main": T("online.t_main"), "create": T("online.t_create"),
                  "join": T("online.t_join"), "list": T("online.t_list"),
                  "lobby": T("online.t_lobby")}
        self.txt(s, titles.get(self.opage, "ONLINE"), self.font, C.WHITE, C.W // 2, py + 24)
        self.orow_rects = []
        if self.opage in ("main", "create", "join"):
            items = self._oitems()
            for i, item in enumerate(items):
                ry = py + 62 + i * 48
                sel = (i == self.ofocus)
                if item[0] in ("text", "opt"):
                    k = item[1]
                    self.txt(s, T(self.OFIELD_TXT[k]), self.font, C.WHITE, px + 110, ry + 14)
                    box = pygame.Rect(px + 200, ry - 2, 370, 34)
                    draw.rect(s, (40, 60, 110) if sel else (30, 36, 60), box,
                                     border_radius=8)
                    draw.rect(s, C.YELLOW if sel else (90, 100, 140), box, 2,
                                     border_radius=8)
                    if item[0] == "opt":
                        shown = self._o_mode_label()
                        self.txt_fit(s, shown, 350, 20, C.WHITE, px + 385, ry + 15)
                    else:
                        val = self.ofields[k]
                        shown = ("•" * len(val)) if k == "senha" and val else (val or "…")
                        if sel and (pygame.time.get_ticks() // 500) % 2 == 0:
                            shown += "_"
                        self.txt_fit(s, shown or " ", 350, 20, C.WHITE, px + 385, ry + 15)
                    self.orow_rects.append(("focus", i, box))
                else:
                    bar = pygame.Rect(px + 30, ry - 2, pw - 60, 36)
                    if sel:
                        draw.rect(s, (50, 90, 190), bar, border_radius=9)
                    draw.rect(s, C.YELLOW if sel else (90, 100, 140), bar, 2,
                                     border_radius=9)
                    self.txt(s, item[1], self.font, C.WHITE, px + pw // 2, ry + 16)
                    self.orow_rects.append(("focus", i, bar))
            hints = {"main": T("online.hint_main").format(auth=net.auth_status()),
                     "create": T("online.hint_create"),
                     "join": T("online.hint_join")}
            self.txt(s, hints.get(self.opage, ""), self.f_sm, (150, 160, 190),
                     C.W // 2, py + ph - 44)
            if self.opage == "main":
                checked, ok, _ms, _e = self.relay_state
                self.txt_fit(s, self.relay_line(), pw - 60, 17,
                             (120, 255, 170) if ok else ((170, 180, 205) if not checked else (255, 150, 130)),
                             C.W // 2, py + ph - 66)
        elif self.opage == "list":
            if not self.orooms:
                self.txt(s, T("online.no_rooms"), self.font, (170, 180, 205),
                         C.W // 2, py + 120)
            for i, (code, room) in enumerate(self.orooms[:8]):
                ry = py + 62 + i * 38
                sel = (i == self.oroom_sel)
                rect = pygame.Rect(px + 24, ry - 2, pw - 48, 32)
                if sel:
                    draw.rect(s, (50, 90, 190), rect, border_radius=8)
                host = (room.get("host") or {}).get("name", "?")
                lock = "[senha]" if room.get("hasPassword") else "[aberta]"
                tag = f" #{room.get('tag')}" if room.get("tag") else ""
                self.txt_fit(s, f"{lock} {room.get('name', '?')}  [{code}]{tag}  {host}  {room.get('status', '')}",
                             pw - 80, 18, C.WHITE if sel else (170, 180, 205),
                             C.W // 2, ry + 14)
                self.orow_rects.append(("room", i, rect))
            self.txt(s, T("online.list_footer"), self.f_sm, (150, 160, 190),
                     C.W // 2, py + ph - 44)
        elif self.opage == "lobby":
            code = self.olobby["code"] if self.olobby else "?"
            self.txt_fit(s, code, 400, 44, C.YELLOW, C.W // 2, py + 80, True)
            room = getattr(self, "_oroom", None) or {}
            host = (room.get("host") or {}).get("name", "…")
            guest = (room.get("guest") or {}).get("name", T("online.lobby_wait_guest"))
            tag = f" #{room.get('tag')}" if room.get("tag") else ""
            self.txt(s, f"{host}  x  {guest}{tag}", self.font, C.WHITE, C.W // 2, py + 130)
            if self._lobby_ready():
                self.txt(s, T("online.lobby_ready"), self.f_score, (120, 255, 170),
                         C.W // 2, py + 200)
            else:
                role = self.olobby["role"] if self.olobby else "?"
                wait = T("online.lobby_wait_host") if role == "host" else T("online.lobby_wait_guest")
                self.txt(s, wait, self.font, (170, 180, 205), C.W // 2, py + 200)
            self.txt(s, T("online.lobby_code_hint"),
                     self.f_sm, (150, 160, 190), C.W // 2, py + 250)
            self.txt(s, T("online.lobby_footer"), self.f_sm,
                     (150, 160, 190), C.W // 2, py + ph - 44)
            checked, ok, _ms, _e = self.relay_state
            self.txt_fit(s, self.relay_line(), pw - 60, 17,
                         (120, 255, 170) if ok else ((170, 180, 205) if not checked else (255, 150, 130)),
                         C.W // 2, py + ph - 66)
        if self.omsg:
            self.txt_fit(s, self.omsg, pw - 60, 18, (255, 200, 120), C.W // 2, py + ph - 20)
