"""CaVo — Carvalhinhos* Voadores. Entrada fina: rode `python main.py`.

Estrutura:
  cavo/config.py    -> tuning (física, jato, stamina, dano, kits, bots, labirinto)
  cavo/settings.py  -> vídeo/gráficos persistidos (settings.json)
  cavo/input.py     -> teclado+mouse+TOUCH+GAMEPAD -> Intent
  cavo/particles.py -> faíscas, jato branco, bolona carregada
  cavo/player.py    -> o T (mira, flap, stamina, HP+vidas)
  cavo/arena.py     -> balõezinhos do treino
  cavo/maze.py      -> labirinto procedural
  cavo/bots.py      -> IA dos bots
  cavo/game.py      -> partida, HUD Osu!, menu XMB
  sprites_tool.py   -> importa/organiza PNGs (duplo clique abre a janelinha)
  texts_gui.py      -> editor visual do texts.json

Controles:
  MENU XMB: mouse ←/→ + ENTER (ou clique) • 1/2/3 atalhos • F11 vídeo • gamepad A/B
  TREINO: mouse gira 360° (A/D tb) • SEGURAR Click/S = JATO • ESPAÇO/W flap
        AÇÃO (Shift/E/RMB): estabiliza p/ mirar; segure e SOLTE o jato = BOLONA
  TOUCH: arrastar mira • botões JATO/PULO/AÇÃO
  GAMEPAD: stick direito mira • RT/RB jato • A pulo • LB ação
  VERSUS (split-screen): P1 como no treino • P2: setas (↓ jato, ↑ flap, RShift// ação)
  Pulo automático mantém o voo (com AÇÃO paira, sem AÇÃO afunda devagar).
  Topo/lados empurram de volta; cair embaixo do mapa = -1 vida.
  Stamina: jato drena; regen rápida se sobrar; zerou = lockout ~5s.
  Versus: dano no HP; zerou = -1 vida; 3 vidas; sem vidas = game over.
  [R] revanche • [M]/[ESC] menu
"""
import sys
import os
from types import SimpleNamespace

import pygame

from cavo import config as C
from cavo.game import Game
from cavo.input import (init_pads, poll_pads, read_intents, touch_event,
                        touch_reset, pad_tokens, DeviceFocus, PadMenu)
from cavo.settings import Settings
from cavo.performance import FrameStats, Presenter
from cavo.video import Display
from cavo.app_platform import quit_game

WEB = sys.platform == "emscripten"  # browser (pygbag): sem socket/requests


def main():
    import asyncio
    asyncio.run(_run())


async def _run():
    import asyncio
    os.environ["SDL_TOUCH_MOUSE_EVENTS"] = "0"
    os.environ["SDL_MOUSE_TOUCH_EVENTS"] = "0"
    pygame.init()
    st = Settings.load()
    display = Display(st)
    screen, canvas = display.screen, display.canvas
    pygame.display.set_caption("CaVo")
    clock = pygame.time.Clock()
    game = Game(st)
    init_pads()
    focus = DeviceFocus(pygame.mouse.get_pos())
    pad_menu = PadMenu()
    previous_pad = set()
    previous_state = (game.state, game.section)
    mobile = False
    browser_debug = None
    stats, presenter = FrameStats(), Presenter()
    from cavo.performance import FrameMeter
    meter = FrameMeter()
    if WEB:
        import platform
        from cavo.browser import BrowserDebug
        browser_debug = BrowserDebug(platform.window)
        mobile = bool(platform.window.cavoHasTouch())

    while True:
        if WEB:
            elapsed = clock.tick() / 1000.0  # browser dita o ritmo (rAF)
        else:
            elapsed = clock.tick(C.FPS) / 1000.0
        stats.tick(elapsed)
        meter.mark("idle")
        dt = min(0.033, elapsed)
        events = pygame.event.get()
        pads = poll_pads()
        display.refresh()
        screen, canvas = display.screen, display.canvas
        game.set_viewport(display.geometry.world_size)
        dw, dh = screen.get_size()

        def to_canvas(px, py):
            return display.ui_point((px, py))

        focus.prepare(events)
        for ev in events:
            focus.event(ev)
            if ev.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED) and not WEB:
                init_pads()
        pad0 = pads[0] if pads else None
        # Pad ativo vence eventos de ponteiro emulados pelo navegador no mesmo frame.
        focus.observe_pad(pad0)
        pygame.mouse.set_visible(focus.source not in ("gamepad", "touch"))
        capturing = (game.state == "menu" and game.section == "settings" and
                     game.settings_menu.name == "controls" and
                     game.controls.capture_pad(pad0))
        menu_keys = pad_menu.update(dt, pad0, st.controls)
        pressed = pad_tokens(pad0)
        if not capturing and game.state != "menu" and (pressed-previous_pad).intersection(st.controls["gamepad"]["retry"]):
            events.append(SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_r, command="retry"))
        previous_pad = pressed
        for key in ([] if capturing else menu_keys):
            command = None
            if game.state != "menu":
                if key not in (pygame.K_ESCAPE, pygame.K_PAUSE):
                    continue
                key = pygame.K_ESCAPE  # B/Start volta ao menu durante a partida
                command = "menu"
            elif key == pygame.K_PAUSE:
                key = pygame.K_RETURN
            elif key == pygame.K_ESCAPE and game.section == "root":
                continue
            events.append(SimpleNamespace(type=pygame.KEYDOWN, key=key, unicode="", mod=0, command=command))

        for ev in events:
            if ev.type == pygame.QUIT:
                quit_game()
            if ev.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED):
                touch_reset()
                focus.fingers.clear()
                game.controls.drag = None
                game.settings_menu.gesture = None
            if ev.type == pygame.MOUSEWHEEL and game.state == "menu" and game.section == "settings":
                game.settings_menu.scroll(-ev.y)
                continue
            if ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                if not focus.accepts_mouse(ev):
                    continue
                if game.state == "menu" and game.section == "settings":
                    kind = {pygame.MOUSEMOTION: "move", pygame.MOUSEBUTTONDOWN: "down", pygame.MOUSEBUTTONUP: "up"}[ev.type]
                    if ev.type == pygame.MOUSEMOTION or ev.button == 1:
                        game.settings_pointer(kind, "mouse", to_canvas(*ev.pos))
                    continue
            if ev.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
                kind = {pygame.FINGERDOWN: "down", pygame.FINGERMOTION: "move",
                        pygame.FINGERUP: "up"}[ev.type]
                pos = to_canvas(ev.x * dw, ev.y * dh)
                if game.state == "menu":
                    if game.section == "settings":
                        game.settings_pointer(kind, ev.finger_id, pos)
                    elif kind == "down":
                        if game.menu_click(pos) == "quit":
                            quit_game()
                elif game.state == "over" and kind == "down":
                    game.state, game.section = "menu", "root"
                elif game.state in ("treino", "versus", "online"):
                    player = game.o_local if game.state == "online" else game.players[0]
                    role = touch_event(kind, ev.finger_id, pos, st.controls, player.angle,
                                       display.geometry.world_size)
                    if role == "menu" and kind == "down":
                        if game.state == "online":
                            game.leave_online()
                        game.state, game.section = "menu", "root"
                continue
            if ev.type == pygame.KEYDOWN:
                if game.state == "menu" and game.section == "settings":
                    if game.controls.capture and getattr(ev, "repeat", False):
                        continue
                    if not game.settings_menu.key(ev.key):
                        game.section = "root"
                    continue
                if ev.key == pygame.K_F11:
                    st.cycle_video()
                    continue
                command = getattr(ev, "command", None)
                kb_menu = st.controls["keyboard1"]["menu"] + st.controls["keyboard2"]["menu"]
                kb_retry = st.controls["keyboard1"]["retry"] + st.controls["keyboard2"]["retry"]
                if ev.key == pygame.K_ESCAPE or command == "menu" or (game.state != "menu" and ev.key in kb_menu):
                    if game.state == "menu":
                        if not game.esc_menu():
                            quit_game()
                    else:
                        if game.state == "online":
                            game.leave_online()
                        game.state = "menu"
                        game.section = "root"
                elif game.state == "menu":
                    if game.section == "online":
                        game.online_key(ev)
                    elif game.section == "treino":
                        game.treino_key(ev)
                    elif game.handle_menu_key(ev.key) == "quit":
                        quit_game()
                elif ev.key in kb_retry or command == "retry":
                    if game.state == "over" and game.last_mode == "online":
                        game.leave_online()   # fecha a sessão (nuvem/relay)
                        game.state = "menu"
                        game.section = "root"
                    elif game.state == "treino" and game.tmode == "labirinto":
                        game.retry_maze_level()
                    else:
                        game.reset(game.last_mode if game.state == "over" else game.state)
                elif game.state == "over" and ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if game.last_mode == "online":
                        game.leave_online()
                    game.state = "menu"
                    game.section = "root"
            if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and game.state == "menu"
                    and focus.source != "gamepad"):
                if game.menu_click(to_canvas(*ev.pos)) == "quit":
                    quit_game()
        meter.mark("ev")

        if st._dirty:
            display.refresh()
            screen, canvas = display.screen, display.canvas
        game.set_viewport(display.geometry.world_size)
        if previous_state != (game.state, game.section):
            touch_reset()  # dedo que abriu a partida não vira mira/jato
            previous_state = (game.state, game.section)
        game.touch_visible = (mobile or focus.source == "touch") and focus.source != "gamepad"

        if game.state == "menu":
            game.menu_tick(dt)
            if focus.source == "mouse":
                game.menu_hover(to_canvas(*pygame.mouse.get_pos()))
        elif game.state in ("treino", "versus", "online"):
            keys = pygame.key.get_pressed()
            mbtn = pygame.mouse.get_pressed()
            mpos = game.to_world(display.world_point(pygame.mouse.get_pos()), 0)
            if game.state == "online" and game.o_local is not None:
                ppos = [(game.o_local.p.x, game.o_local.p.y)]
            elif game.state == "versus":
                ppos = [(game.players[0].p.x, game.players[0].p.y),
                        (game.players[1].p.x, game.players[1].p.y)]
            else:
                ppos = [(game.players[0].p.x, game.players[0].p.y)]
            i1, i2 = read_intents("treino" if game.state == "online" else game.state,
                                  keys, mbtn, mpos, pads=pads, player_pos=ppos,
                                  mouse_enabled=focus.source in ("mouse", "keyboard"),
                                  controls=st.controls, source=focus.source)
            game.update(dt, i1, i2)
        meter.mark("up")
        game.draw(canvas)
        game.draw_diagnostics(canvas, stats, focus.source)
        meter.mark("draw")

        presenter.draw(screen, canvas, st.smooth_scaling)
        meter.mark("pres")
        pygame.display.flip()
        meter.mark("flip")
        meter.emit(stats.fps, f"canvas={canvas.get_size()} screen={screen.get_size()} "
                              f"driver={pygame.display.get_driver()} "
                              f"smooth={st.smooth_scaling} quality={st.quality} "
                              f"res={st.resolution}")
        if browser_debug:
            browser_debug.report(game, focus.source, screen, stats.fps)
        await asyncio.sleep(0)  # pygbag: devolve o controle p/ o browser


if __name__ == "__main__":
    main()
