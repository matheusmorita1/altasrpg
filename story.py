"""Historia: a cena de abertura (Capitulo 1 - A Noite dos Goblins).

Arthur dorme em casa. Na volta para casa, de noite, o pai dele (Edmundo) e levado por
goblins na estrada leste. O vizinho Joaquim ve tudo, corre ate a casa de Arthur, acorda
o rapaz e conta o que aconteceu. Arthur sai para a vila: comeca a aventura.
"""
import math

from ursina import Entity, Vec3, color, curve

import sounds
from cutscene import Actor, Cutscene, smooth
from enemies import Goblin
from models import Glow, flat, part, set_dormant
from settings import C, PLAYER_SPAWN, PLAYER_SPAWN_YAW
from ui import FloatingText

FATHER = 'Edmundo'
NEIGHBOR = 'Joaquim'
INTRO_OBJECTIVE = 'Resgate seu pai: siga a estrada a leste até o Acampamento Goblin'
DAWN_DURATION = 90           # segundos ate o dia clarear depois da cena

# ---------------------------------------------------------------- lugares
GOBLIN_ROAD = Vec3(48, 0, 22).normalized()          # direcao da estrada para o acampamento


def road(distance):
    return GOBLIN_ROAD * distance


ARTHUR_DOOR = Vec3(-8.45, 0, -1.22)                  # porta da casa de Arthur (telhado azul, oeste)
NEIGHBOR_DOOR = Vec3(3.9, 0, 6.85)                   # na frente da casa de Joaquim (norte da praca)
ROOM = Vec3(0, -60, 0)                               # quarto montado embaixo do mapa (so para a cena)


# ---------------------------------------------------------------- atores
class PuppetGoblin(Goblin):
    """Goblin de cena: mesmo modelo, sem IA."""
    carrying = False

    def update(self):
        from ursina import time
        self.anim_t += time.dt
        self.state = 'chase'
        self.animate_body(time.dt)
        if self.carrying:
            for arm in self.arms:
                arm.rotation_x = -165


def build_room():
    """Quarto do Arthur: cama, mesinha com vela, janela com luar, bau e porta."""
    root = Entity(position=ROOM)
    wood, dark = C['wood'], C['wood_dark']
    wall = color.rgb32(196, 176, 150)
    part(parent=root, scale=(6, 0.1, 6), y=-0.05, color=wood.tint(-0.1))                    # piso
    part(parent=root, scale=(6, 0.1, 6), y=3.05, color=dark)                                # teto
    part(parent=root, scale=(6, 3, 0.2), position=(0, 1.5, -3), color=wall)                 # fundo
    part(parent=root, scale=(6, 3, 0.2), position=(0, 1.5, 3), color=wall)                  # frente
    part(parent=root, scale=(0.2, 3, 6), position=(-3, 1.5, 0), color=wall)                 # esquerda
    for z0, z1 in ((-3, -0.6), (0.6, 3)):                                                   # direita, com porta
        part(parent=root, scale=(0.2, 3, z1 - z0), position=(3, 1.5, (z0 + z1) / 2), color=wall)
    part(parent=root, scale=(0.2, 0.8, 1.2), position=(3, 2.6, 0), color=wall)
    for x in (-2, 0, 2):                                                                    # vigas
        part(parent=root, scale=(0.25, 0.25, 6), position=(x, 2.85, 0), color=dark)
    # porta (gira na dobradica)
    hinge = Entity(parent=root, position=(3, 0, -0.6))
    part(parent=hinge, scale=(0.1, 2.2, 1.2), position=(0, 1.1, 0.6), color=dark)
    flat(parent=root, scale=(0.05, 2.2, 1.2), position=(3.3, 1.1, 0), color=color.rgb32(20, 28, 55))  # noite la fora
    # cama
    part(parent=root, scale=(1.3, 0.45, 2.5), position=(-1.9, 0.22, 0.45), color=wood)
    part(parent=root, scale=(1.2, 0.15, 2.4), position=(-1.9, 0.52, 0.45), color=color.rgb32(235, 230, 215))
    part(parent=root, scale=(1.3, 0.9, 0.12), position=(-1.9, 0.45, -0.85), color=dark)      # cabeceira
    part(parent=root, scale=(0.8, 0.14, 0.38), position=(-1.9, 0.66, -0.55), color=color.rgb32(245, 245, 240))
    blanket = part(parent=root, scale=(1.26, 0.14, 1.6), position=(-1.9, 0.83, 0.85),
                   color=color.rgb32(70, 100, 170))
    # mesinha e vela
    part(parent=root, scale=(0.55, 0.65, 0.5), position=(-2.55, 0.32, -1.45), color=dark)
    part('cylinder', parent=root, scale=(0.09, 0.22, 0.09), position=(-2.55, 0.65, -1.45),
         color=color.rgb32(240, 235, 210))
    flat('cone', parent=root, scale=(0.07, 0.12, 0.07), position=(-2.55, 0.88, -1.45), color=C['fire'])
    candle = Glow(ROOM + Vec3(-2.55, 0.95, -1.45), color.rgb32(255, 170, 80), size=1.6, strength=0.75,
                  flicker=True)
    candle.world_parent = root          # apagado junto com o quarto
    # janela com luar
    part(parent=root, scale=(1.3, 1.1, 0.1), position=(0.6, 1.8, -2.92), color=dark)
    flat(parent=root, scale=(1.1, 0.9, 0.05), position=(0.6, 1.8, -2.88), color=color.rgb32(60, 80, 140))
    part(parent=root, scale=(0.06, 0.9, 0.08), position=(0.6, 1.8, -2.85), color=dark)
    # bau e tapete
    part(parent=root, scale=(0.95, 0.6, 0.55), position=(1.9, 0.3, -2.4), color=wood)
    part(parent=root, scale=(1.0, 0.1, 0.6), position=(1.9, 0.62, -2.4), color=dark)
    part(parent=root, scale=(2.2, 0.02, 1.5), position=(0.3, 0.01, 0.6), color=color.rgb32(150, 50, 45))
    return root, hinge, blanket


# ----------------------------------------------------------------- roteiro
def intro_script(cs):
    game = cs.game
    p = game.player

    # ---------- preparacao
    father = Actor(road(28), shirt=color.rgb32(110, 80, 60), pants=color.rgb32(60, 50, 45),
                   hair=color.rgb32(90, 85, 80))
    part(parent=father.head, scale=(0.36, 0.2, 0.1), position=(0, -0.16, 0.18), color=color.rgb32(90, 85, 80))  # barba
    father.speed_anim = 7
    lantern = flat(parent=father.arms[0], scale=0.18, y=-0.75, color=color.rgb32(255, 220, 140))
    neighbor = Actor(NEIGHBOR_DOOR, shirt=color.rgb32(160, 130, 70), pants=color.rgb32(80, 70, 55),
                     hair=color.rgb32(60, 40, 25))
    neighbor.rotation_y = 70
    room, door_hinge, blanket = build_room()
    cs.actors += [father, neighbor, room]

    # Arthur dormindo na cama
    p.held.enabled = False
    p.blob.enabled = False
    p.position = ROOM + Vec3(-1.9, 0.6, 1.55)
    p.rotation_y = 0
    p.body.rotation_x = -90

    # ================================================= 1. a vila a meia-noite
    yield cs.camera((-4, 9, -15), look=(6, 1, 4))
    game.focus_shadows(road(20))
    cs.go(cs.camera((2, 7, -9), look=(12, 1, 6), duration=6))
    yield cs.fade(0, 2.5)
    yield cs.title_card('Vila de Carvalho', 'Meia-noite', duration=3.5)

    # ================================================= 2. Edmundo volta pela estrada
    walk = cs.go(cs.walk(father, road(20), speed=1.6))
    yield cs.camera((13, 1.9, 4.5), look=father)
    yield cs.track(father)
    yield cs.say(FATHER, 'Que noite fria... o Arthur já deve estar dormindo.')
    yield walk

    # ================================================= 3. os goblins atacam
    hiding = [Vec3(22, 0, 3.5), Vec3(21, 0, 14), Vec3(14.5, 0, 13), Vec3(13.5, 0, 5)]
    goblins = [PuppetGoblin(game, h, None) for h in hiding]
    cs.actors += goblins
    sounds.goblin_laugh()
    yield cs.camera((11, 2.6, 2.5), look=road(20) + Vec3(0, 0.8, 0), duration=1.0)
    ring = [road(20) + Vec3(math.cos(a) * 1.4, 0, math.sin(a) * 1.4) for a in (0.2, 1.8, 3.4, 5.0)]
    runs = [cs.go(cs.walk(g, target, speed=5)) for g, target in zip(goblins, ring)]
    yield cs.face(father, goblins[0])
    yield cs.say('Goblin', 'Hihihi! Olha só o que temos aqui!')
    yield cs.all(*runs)
    for g in goblins:
        cs.face(g, father)
    yield cs.say(FATHER, 'Goblins?! Para trás! Me deixem em paz!')
    yield cs.say('Goblin', 'Pega ele! O chefe vai gostar desse aí!')
    sounds.hit()
    yield cs.all(cs.shake(0.35, 0.25), cs.fade(1, 0.35))

    # ================================================= 4. Joaquim ve tudo
    lantern.enabled = False
    father.body.rotation_x = 90            # carregado de bruços, por cima dos goblins
    father.position = road(20) + Vec3(0, 1.0, 0)
    father.rotation_y = math.degrees(math.atan2(GOBLIN_ROAD.x, GOBLIN_ROAD.z))
    carriers = [Vec3(0.45, 0, -0.5), Vec3(-0.45, 0, 0.6), Vec3(1.4, 0, 0.8), Vec3(-1.2, 0, -1.0)]
    for g, off in zip(goblins, carriers):
        g.position = road(20) + off
        g.carrying = g in goblins[:2]
    yield cs.camera(NEIGHBOR_DOOR + Vec3(-2.6, 1.9, -1.4), look=Vec3(12, 1.2, 8))
    game.focus_shadows(NEIGHBOR_DOOR)
    yield cs.fade(0, 0.6)
    escape = [cs.go(cs.walk(g, road(42) + off, speed=3.0)) for g, off in zip(goblins, carriers)]
    escape.append(cs.go(cs.walk(father, road(42) + Vec3(0, 1.0, 0), speed=3.0)))
    yield 0.4
    yield cs.face(neighbor, road(25))
    yield cs.say(NEIGHBOR, 'Pelos deuses... estão levando o Edmundo!')
    yield cs.camera(NEIGHBOR_DOOR + Vec3(2.6, 1.6, -1.4), look=neighbor, duration=1.2)   # de frente
    yield cs.say(NEIGHBOR, 'Preciso avisar o Arthur. Rápido!')
    run = cs.go(cs.walk(neighbor, ARTHUR_DOOR + Vec3(1.2, 0, 0), speed=5.5))
    yield 1.0
    yield cs.fade(1, 0.8)
    cs.cancel(run, *escape)

    # ================================================= 5. o quarto de Arthur
    game.set_daylight(0)
    game.ambient.color = color.rgb(0.3, 0.25, 0.22)    # luz quente da vela
    neighbor.position = ROOM + Vec3(3.6, 0, 0)
    neighbor.rotation_y = -90
    yield cs.lens(74)
    yield cs.camera(ROOM + Vec3(1.7, 2.2, 2.5), look=ROOM + Vec3(-1.9, 0.6, -0.1))
    yield cs.fade(0, 1.5)
    for i in range(3):
        FloatingText(ROOM + Vec3(-1.9, 1.1, -0.3), 'z' * (i + 1), text_color=color.rgb32(200, 210, 255),
                     scale=1.2 + i * 0.3, lifetime=1.6)
        yield 0.6
    sounds.door()
    yield cs.call(lambda t: setattr(door_hinge, 'rotation_y', -100 * curve.out_back(t)), 0.35)
    yield cs.walk(neighbor, ROOM + Vec3(0.25, 0, 0.6), speed=4.5)
    yield cs.face(neighbor, ROOM + Vec3(-1.9, 0, 0.2))
    yield cs.camera(ROOM + Vec3(1.0, 2.1, 2.7), look=ROOM + Vec3(-1.5, 0.8, 0.0), duration=0.6)
    yield cs.say(NEIGHBOR, 'Arthur! Arthur, acorda!')

    # Arthur levanta da cama
    bed_pos, stand_pos = Vec3(p.position), ROOM + Vec3(-0.95, 0, 0.6)

    def get_up(t):
        k = smooth(t)
        p.body.rotation_x = -90 * (1 - k)
        p.position = bed_pos + (stand_pos - bed_pos) * k
        p.rotation_y = 90 * k                        # vira para o Joaquim
        blanket.position = Vec3(-1.9, 0.83, 0.85 + 0.5 * k)
    yield cs.call(get_up, 1.0)
    neighbor.rotation_y = -90
    yield cs.camera(ROOM + Vec3(-0.35, 1.5, 2.8), look=ROOM + Vec3(-0.35, 1.25, 0.6), duration=0.8)
    yield cs.say('Arthur', 'Hmm... Joaquim? O que houve? Ainda é noite...')
    yield cs.say(NEIGHBOR, 'É o seu pai! Eu vi tudo da minha porta... um bando de goblins pegou ele na estrada!')
    yield cs.camera(ROOM + Vec3(0.0, 1.7, 2.4), look=ROOM + Vec3(-0.95, 1.45, 0.6), duration=0.6)
    yield cs.say('Arthur', 'O quê?! O meu pai?!')
    yield cs.camera(ROOM + Vec3(-0.35, 1.5, 2.8), look=ROOM + Vec3(-0.35, 1.25, 0.6), duration=0.6)
    yield cs.say(NEIGHBOR, 'Eles foram para o leste, na direção do acampamento deles.')
    yield cs.say('Arthur', 'Eu preciso ir atrás dele. Agora!')
    yield cs.say(NEIGHBOR, 'Você só tem aquela velha espada de madeira... Passe nas lojas da praça antes. '
                           'E tome cuidado, garoto.')
    yield cs.fade(1, 1.0)

    # ================================================= 6. Arthur sai para a vila
    game.set_daylight(0)
    neighbor.position = ARTHUR_DOOR + Vec3(1.1, 0, 1.6)
    neighbor.rotation_y = 200
    p.held.enabled = True
    p.position = ARTHUR_DOOR
    p.rotation_y = PLAYER_SPAWN_YAW
    game.focus_shadows(ARTHUR_DOOR)
    yield cs.lens(58)
    yield cs.camera(Vec3(-2.0, 2.0, -0.6), look=ARTHUR_DOOR + Vec3(1.0, 1.0, 0))
    yield cs.fade(0, 1.0)
    out = Vec3(*PLAYER_SPAWN)
    run_dir = out - ARTHUR_DOOR
    p.rotation_y = math.degrees(math.atan2(run_dir.x, run_dir.z))

    def run_out(t):
        p.position = ARTHUR_DOOR + run_dir * t
        p._animate_walk(1 / 60, t < 1, True)
    yield cs.call(run_out, 1.1)
    start_yaw = p.rotation_y
    yield cs.call(lambda t: setattr(p, 'rotation_y', start_yaw + (PLAYER_SPAWN_YAW - start_yaw) * smooth(t)), 0.5)
    yield cs.face(neighbor, p)
    cs.go(cs.say(NEIGHBOR, 'Que os deuses te protejam, Arthur!', auto=1.6))
    # camera vai para tras do heroi (posicao do jogo)
    p.cam_pivot.rotation = (18, PLAYER_SPAWN_YAW, 0)
    p.cam_pivot.position = out + Vec3(0, 2.2, 0)
    p.cam_distance = 9
    behind = p.cam_pivot.position - p.cam_pivot.forward * p.camera_clearance(9)   # sem atravessar a casa
    yield cs.camera(behind, look=p.cam_pivot.position, duration=2.0)
    yield cs.title_card('Capítulo 1', 'A Noite dos Goblins', duration=3.2)


def finish_intro(game):
    """Estado final da abertura (usado ao terminar e ao pular a cena)."""
    p = game.player
    p.body.rotation_x = 0
    p.held.enabled = True
    p.blob.enabled = True
    if p.position.y < -10 or (p.position - Vec3(*PLAYER_SPAWN)).length() > 4:
        p.position = Vec3(*PLAYER_SPAWN)
        p.rotation_y = PLAYER_SPAWN_YAW
    p.cam_pivot.rotation = (18, PLAYER_SPAWN_YAW, 0)
    p.cam_pivot.position = p.position + Vec3(0, 2.2, 0)
    p.cam_distance = 9


def play_intro(game, on_done):
    """Toca a abertura. on_done() e chamado quando o jogador assume o controle."""
    for enemy in game.enemies:              # monstros congelados durante a cena
        set_dormant(enemy, True)
    game.set_daylight(0)
    game.hud.enabled = False
    game.music.set_override(0.06, duration=1.0)

    def ended(skipped):
        finish_intro(game)
        game.set_daylight(0)
        game.start_dawn(DAWN_DURATION)
        game.music.set_override(None, duration=3.0)
        game.hud.enabled = True
        game.cutscene = None
        on_done()

    game.cutscene = Cutscene(game, intro_script, on_end=ended, finish=lambda: finish_intro(game))
