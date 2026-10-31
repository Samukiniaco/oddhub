"""CaVo — tuning central. Mexa aqui p/ balancear o jogo.

Convenção de ângulo (360°, + = sentido horário na tela):
  angle = direção da PONTA (caninho do jato), em graus,
  medida a partir de "para baixo".
  0 = ponta p/ baixo | +90 = p/ esquerda | 180/-180 = p/ cima | -90 = p/ direita.
  (A ponta segue o mouse; o jato sai sempre dela.)

Pulo automático (ritmo CALCULADO p/ skins futuras):
  interval = flap_imp / (grav * sink)  ->  impulso médio = grav*sink (afunda 1-sink)
  com AÇÃO segurada o impulso é flap_imp/sink  ->  impulso médio = grav (pai­ra).
  Troque flap_imp/grav/sink por skin e o ritmo se ajusta sozinho.
"""
# canvas interno (o mundo é maior; a câmera recorta)
W, H = 900, 650
FPS = 60

# mundo grande (sem chão/plataformas; cair embaixo mata)
WORLD_W = 3600.0
WORLD_H = 2600.0
DEATH_MARGIN = 150.0     # y > WORLD_H + isso = caiu do mapa (-1 vida)
SOFT_PUSH_BASE = 250.0   # empurrão de volta no topo/laterais (sem matar)
SOFT_PUSH_GAIN = 2.5     # cresce com a distância p/ fora
SOFT_PUSH_MAX = 1200.0

# câmera: T no centro + saidinha na direção do movimento
CAM_LEAD = 0.35          # fração da velocidade somada à visão (vê mais p/ onde vai)
CAM_LEAD_MAX = 130.0     # teto do deslocamento (px)
CAM_SMOOTH = 5.0         # maior = mais grudada

# setas fora da tela (onde tá o outro? aponta p/ ele)
ARROW_MARGIN = 40
ARROW_SIZE = 16

# física dos T
GRAV = 950.0
AIR_DRAG = 0.45          # arrasto normal
AIR_DRAG_JETTING = 0.12  # arrasto enquanto o jato empurra (deixa ir bem rápido)
MAX_SPEED = 780.0
PLAYER_R = 20
TIP_DIST = 26            # distância centro -> pontinha do jato

# mira / giro
ROT_SPEED_KEY = 320.0    # graus/segundo no teclado (A/D, setas)
MOUSE_AIM_SPEED = 18.0   # suavização da mira do mouse (maior = mais duro)

# controles: zona morta e repetição de navegação no menu
PAD_DEADZONE = 0.25
PAD_AIM_RANGE = 350.0
PAD_MENU_THRESHOLD = 0.55
PAD_MENU_DELAY = 0.35
PAD_MENU_REPEAT = 0.12
PAD_MAX_BUTTONS = 32
TOUCH_MOUSE_GUARD = 0.65  # ignora clique/movimento sintetizado após tocar
TOUCH_STICK_DEAD = 0.16
TOUCH_SWIPE_SENS = 0.65  # graus por pixel do canvas, deslize horizontal
TOUCH_SIZE_STEP = 5
TOUCH_MIN_RADIUS = 24
TOUCH_MAX_RADIUS = 100
TOUCH_LAYOUT_GAP = 5
TOUCH_BORDER_ALPHA = 85
TOUCH_KNOB_ALPHA = 120
FPS_SAMPLE_SECONDS = 0.5
TEXT_CACHE_SIZE = 256
TOUCH_DEFAULT_LAYOUT = {
    "aim": [145, 495, 85], "jet": [795, 460, 58],
    "flap": [675, 555, 46], "action": [815, 585, 38],
    "menu": [50, 125, 28],
}
SETTINGS_VISIBLE_ROWS = 7
SETTINGS_ROW_HEIGHT = 58
HUD_SCALE_VALUES = (0.75, 0.9, 1.0, 1.1, 1.25)
TOUCH_OPACITY_VALUES = (0.25, 0.5, 0.75, 1.0)
PARTICLE_DENSITY_VALUES = (0.25, 0.5, 1.0)
SHAKE_STRENGTH_VALUES = (0.25, 0.5, 1.0)
MINIMAP_SIZE = (180, 130)

# asas: pulo AUTOMÁTICO (sempre p/ cima, ritmo calculado) +
#       pulo MANUAL (direcional: p/ onde o topo aponta; rápido de sair).
#       Com stamina paga cheio; zerado sai FRACO de graça (fuga de emergência,
#       afunda devagar — nunca vira voo). Tem que APERTAR toda vez e atravessar
#       o mapa custa stamina de verdade (pulo e/ou jato).
#       Skins futuras de voo mudam estes valores (kit) e os ritmos acompanham.
FLAP_IMP = 400.0
FLAP_MANUAL_IMP = 420.0
FLAP_MANUAL_CD = 0.25
FLAP_STAM_COST = 4.0
FLAP_WEAK_MUL = 0.5      # pulo zerado: metade da força, de graça, só desce devagar
SINK_RATIO = 0.85        # sem AÇÃO o pulo segura 85% da gravidade (afunda devagar)
STABILIZE_DAMP = 4.0     # com AÇÃO: amortecimento lateral p/ mirar estável


def hover_interval(flap_imp=FLAP_IMP, grav=GRAV, sink=SINK_RATIO):
    """Intervalo do pulo automático p/ impulso médio = grav*sink."""
    return flap_imp / (grav * sink)


# JATO branco contínuo (sai da ponta, tem gravidade, é tiro + propulsão)
JET_THRUST = 1500.0      # aceleração empurrando o T (oposto à ponta)
JET_SPEED = 720.0        # velocidade inicial das partículas do jato
JET_EMIT_RATE = 170.0    # partículas/segundo enquanto segurar
JET_LIFE = 0.85          # tempo de vida (forma o rastro)
JET_LIFE_JITTER = 0.25
JET_GRAV = 620.0         # gravidade do jato (o "tiro pesado")
JET_DRAG = 0.4
JET_SIZE = 6
JET_SPREAD = 60.0        # espalhamento lateral na saída
JET_INHERIT = 0.35       # quanto da velocidade do T entra no jato

# combate: HP por dano + vidas (zerou o HP, perde 1 vida; sem vidas = game over)
HP_MAX = 100.0
LIVES_START = 3
CHIP_DMG = 6.0          # cada pingo do jato
CHIP_CD = 0.15          # intervalo mín. entre danos de chip (não derrete)
INV_HEAVY = 1.0         # invencibilidade após tiro carregado / perder vida
SELF_JET_GRACE = 0.4    # rastro só te machuca depois desse tempo

# stamina: gasta no jato, regen rápida se sobrar, lockout ~5s se zerar
STAM_MAX = 100.0
STAM_DRAIN = 42.0       # por segundo segurando o jato (~2.4s de voo)
STAM_REGEN = 65.0       # por segundo (quando NÃO está jateando)
STAM_REGEN_DELAY = 0.35 # espera antes de começar a regen
STAM_INDICATOR_RADIUS = 11
STAM_INDICATOR_WIDTH = 3
STAM_INDICATOR_OFFSET = (52, -10)
STAM_INDICATOR_FONT = 10
STAM_HIDE_DELAY = 1.5   # cheia e sem uso: espera e depois esvanece
STAM_FADE_TIME = 0.4
EXHAUST_MIN = 4.0       # lockout aleatório quando zera, base 5s...
EXHAUST_MAX = 6.0       # ...entre 4 e 6 segundos (gameplay frenética)

# tiro CARREGADO: segura AÇÃO + solta o jato -> gasta TUDO numa bolona
CHARGE_MIN_STAM = 15.0
CHARGE_CD = 1.0
CHARGE_SPEED = 780.0
CHARGE_DMG_BASE = 25.0
CHARGE_DMG_SCALE = 35.0
CHARGE_RECOIL_BASE = 380.0
CHARGE_RECOIL_SCALE = 260.0
CHARGE_GRAV_MUL = 0.35
CHARGE_LIFE = 3.0

# treino: balõezinhos
BALLOON_COUNT = 7
BALLOON_NEAR_MIN = 500.0   # nascem nessa faixa de distância do jogador...
BALLOON_NEAR_MAX = 1100.0
BALLOON_FAR = 1800.0       # ...e renascem perto se ficarem mais longe que isso

# treino: LABIRINTO procedural (sempre tem caminho: gera + resolve por construção)
MAZE_COLS = 15
MAZE_ROWS = 11
MAZE_CELL = 140.0
MAZE_WALL = 18.0
MAZE_DIFFS = {
    # orbs: qtd/velocidade | cp_every: checkpoint a cada N células do caminho
    # fallback: p/ checkpoint ou p/ começo | penalty: segundos somados ao cair
    "facil":   {"orbs": 4,  "speed": 90.0,  "cp_every": 4, "fallback": "cp",    "penalty": 2},
    "normal":  {"orbs": 7,  "speed": 130.0, "cp_every": 6, "fallback": "cp",    "penalty": 3},
    "dificil": {"orbs": 10, "speed": 180.0, "cp_every": 8, "fallback": "start", "penalty": 5},
}

# treino: BOTS (deathmatch com vidas, igual ao versus)
BOT_NAMES = ("BOT 1", "BOT 2", "BOT 3", "BOT 4", "BOT 5")
BOT_MAX = 5
BOT_FLAP_INTERVAL = 0.32
BOT_RECOVERY_MARGIN = 900.0
BOT_RECOVERY_EXIT_Y = 1100.0
BOT_REFUEL_BUFFER = 35.0
BOT_RECOVERY_LOOKAHEAD = 0.65
BOT_RECOVERY_ALIGN = 30.0
BOT_CHARGE_DISTANCE = 190.0
BOT_CHARGE_STAMINA = 95.0
BOT_CHARGE_PREPARE = 0.35
BOT_CHARGE_SAFE_HEIGHT = 1500.0
BOT_CHARGE_MAX_FALL = 150.0
BOT_CHARGE_INITIAL_DELAY = (5.0, 9.0)
BOT_CHARGE_INTERVALS = {"facil": (22.0, 30.0), "normal": (16.0, 24.0), "dificil": (12.0, 18.0)}
BOT_SKILLS = {
    # aim_err: graus de erro na mira | lead: quanto antecipa o alvo
    # reserve: stamina mínima p/ jatear | aggro: 0 foge / 1 caça
    "facil":   {"aim_err": 14.0, "lead": 0.4, "reserve": 35.0, "aggro": 0.4},
    "normal":  {"aim_err": 8.0,  "lead": 0.7, "reserve": 25.0, "aggro": 0.7},
    "dificil": {"aim_err": 4.0,  "lead": 0.9, "reserve": 15.0, "aggro": 1.0},
}

# ---------- ONLINE (netcode) ----------
# A nuvem (Firebase) manda o estado por escrita (PATCH) e lê por polling (GET):
# o SSE do RTDB só descarrega ~1x/s, então não serve p/ jogo.
NET_SEND_HZ = 20          # escritas de estado por segundo (cada lado o seu)
NET_POLL_HZ = 30          # leituras por segundo da subárvore da partida
NET_WORKERS = 5           # conexões paralelas p/ escrita e p/ leitura
NET_WORKERS_MAX = 9       # teto (link lento abre mais leitores)
NET_DELAY_BASE = 0.16     # atraso de render do fantasma (base)
NET_DELAY_CLOUD = 0.30    # base da nuvem: ida e volta até o Firebase
NET_DELAY_MIN = 0.08      # piso do atraso adaptativo
NET_DELAY_MAX = 0.45      # teto do atraso adaptativo
NET_EXTRAP_MAX = 0.14     # extrapola no máximo isso (s) quando o buffer seca
NET_SNAP_MAX = 32         # amostras guardadas
NET_CHIP_RANGE = 70.0 + 40.0   # alcance do pingo + folga p/ lag
NET_HEAVY_RANGE = 110.0 + 40.0
NET_HIT_WINDOW = 2.0        # quanto tempo de histórico o árbitro usa p/ julgar o tiro
NET_HEAVY_CD = 1.0        # intervalo entre bolonas
NET_CLAIM_SLOTS = 2       # slots girados por nó (evita limite de escrita do RTDB)
NET_TIMEOUT = 10.0        # timeout das chamadas HTTP
NET_GIVEUP = 12           # falhas seguidas no polling => sessão morta
NET_LOST_SECONDS = 8.0    # sem sinal do oponente => caiu a conexão

# spawns no mundo
SPAWN_TREINO = (1800.0, 500.0)
SPAWN_P1 = (1300.0, 500.0)
SPAWN_P2 = (2300.0, 500.0)

# sprites opcionais (sprites_tool.py). Ponta do jato = PARA BAIXO no arquivo.
SPRITE_SLOTS = ("p1", "p2")
SPRITE_MAX = 56

# cores
CYAN = (64, 224, 255)
ORANGE = (255, 170, 60)
BG = (16, 18, 30)
WHITE = (235, 240, 250)
YELLOW = (255, 230, 120)
