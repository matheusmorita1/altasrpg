"""Constantes gerais do jogo. Ajuste aqui para balancear o jogo."""
from ursina import color

WINDOW_TITLE = 'Lamina de Carvalho - RPG 3D'

# --- Mundo -----------------------------------------------------------------
WORLD_RADIUS = 88          # o jogador nao passa deste raio
VILLAGE_RADIUS = 15        # zona segura: inimigos nao entram
WORLD_SEED = 7             # muda o posicionamento das arvores/pedras

# --- Desempenho / distancia de visao ----------------------------------------
# A nevoa esconde o limite de visao: o que esta alem de VIEW_DISTANCE nao e desenhado,
# e mobs/moedas alem de ACTIVE_DISTANCE ficam congelados (sem custo) ate voce chegar perto.
FOG_START = 26
FOG_END = 58
VIEW_DISTANCE = 64                 # plano de corte da camera (um pouco depois da nevoa total)
ACTIVE_DISTANCE = 62               # mobs e moedas acordam abaixo disso...
SLEEP_DISTANCE = 70                # ...e dormem acima disso (folga evita liga/desliga)
FOG_COLOR = color.rgb32(196, 222, 240)     # cor do horizonte (a nevoa se funde ao ceu)
SKY_TOP_COLOR = color.rgb32(110, 170, 235)
SHADOW_MAP_SIZE = 2048
SHADOW_SAMPLES = 2                 # 2x2 amostras por pixel (o Ursina usa 4x4 = 16)
SHADOW_BLUR = 0.004

# --- Musica ----------------------------------------------------------------
MUSIC_VOLUME = 0.45            # 0 a 1 (tecla M liga/desliga durante o jogo)
MUSIC_PAUSED_VOLUME = 0.15     # mais baixo na pausa e na tela de morte

# --- Camera ----------------------------------------------------------------
MOUSE_SENSITIVITY = 45
CAMERA_DISTANCE = 9
CAMERA_MIN_DISTANCE = 4
CAMERA_MAX_DISTANCE = 16
CAMERA_HEIGHT = 2.2

# --- Jogador ---------------------------------------------------------------
PLAYER_SPAWN = (-5.6, 0, -2.8)   # ao lado da casa de Arthur (telhado azul), olhando para a praca
PLAYER_SPAWN_YAW = 60            # (de costas para um espaco livre: a camera nao bate na casa)
PLAYER_SPEED = 6.0
PLAYER_SPRINT_SPEED = 9.5
PLAYER_JUMP_SPEED = 9.0
GRAVITY = 26.0
PLAYER_START_HP = 100
HP_PER_LEVEL = 15
DAMAGE_PER_LEVEL = 1
START_COINS = 30
CRIT_CHANCE = 0.12

# --- Fome ------------------------------------------------------------------
MAX_HUNGER = 100
HUNGER_DRAIN = 100 / 480      # por segundo: a barra cheia dura ~8 minutos andando
HUNGER_SPRINT_MULT = 2.5      # correr da mais fome
STARVING_DAMAGE = 1.5         # vida perdida por segundo com a fome zerada
WELL_FED_THRESHOLD = 60       # acima disso a vida regenera devagar
WELL_FED_REGEN = 0.006        # fracao da vida maxima por segundo quando bem alimentado
CRIT_MULTIPLIER = 1.8


def xp_for_level(level):
    """XP necessario para passar do nivel `level` para o proximo."""
    return int(20 * level ** 1.5)


# --- Paleta de cores (low-poly) --------------------------------------------
C = {
    'grass':        color.rgb32(108, 170, 82),
    'grass_dark':   color.rgb32(88, 145, 68),
    'grass_light':  color.rgb32(130, 188, 96),
    'path':         color.rgb32(176, 145, 98),
    'dirt':         color.rgb32(120, 98, 72),
    'grave_ground': color.rgb32(92, 104, 84),
    'trunk':        color.rgb32(110, 76, 48),
    'leaves':       color.rgb32(62, 132, 70),
    'leaves_dark':  color.rgb32(46, 106, 60),
    'leaves_light': color.rgb32(96, 160, 72),
    'rock':         color.rgb32(132, 132, 140),
    'rock_dark':    color.rgb32(100, 100, 110),
    'wall':         color.rgb32(232, 220, 190),
    'wood':         color.rgb32(140, 96, 60),
    'wood_dark':    color.rgb32(92, 62, 40),
    'roof':         color.rgb32(176, 74, 58),
    'roof_blue':    color.rgb32(70, 104, 156),
    'window':       color.rgb32(120, 180, 220),
    'stone':        color.rgb32(150, 150, 150),
    'tent':         color.rgb32(122, 104, 60),
    'tent2':        color.rgb32(96, 120, 64),
    'fire':         color.rgb32(255, 150, 40),
    'tombstone':    color.rgb32(160, 160, 168),
    'dead_wood':    color.rgb32(70, 60, 56),
    # Personagem
    'skin':         color.rgb32(240, 196, 150),
    'hair':         color.rgb32(92, 58, 32),
    'tunic':        color.rgb32(60, 120, 190),
    'pants':        color.rgb32(70, 60, 50),
    'belt':         color.rgb32(90, 60, 30),
    'boots':        color.rgb32(60, 40, 28),
}
