"""Inimigos: Slime, Goblin e Esqueleto.

Todos compartilham a mesma IA (classe Enemy):
  vagar -> perseguir -> preparar ataque (aviso visual) -> atacar -> recuperar
Cada tipo so muda os atributos, o modelo 3D e a animacao.
"""
import math
import random

from ursina import Entity, Vec3, color, curve, distance_xz, invoke, lerp, lerp_angle, time

from models import destroy_tree, part
from settings import VILLAGE_RADIUS
from ui import FloatingText
from items import spawn_drops
import sounds


class HealthBar3D(Entity):
    """Barrinha de vida que flutua sobre o inimigo e sempre olha para a camera."""

    def __init__(self, **kwargs):
        super().__init__(billboard=True, **kwargs)
        self.bg = Entity(parent=self, model='quad', scale=(1.0, 0.13), color=color.black66, double_sided=True)
        self.fill = Entity(parent=self, model='quad', origin=(-0.5, 0), x=-0.48, z=-0.01, scale=(0.96, 0.09),
                           color=color.rgb32(220, 50, 50), double_sided=True)
        self.enabled = False

    def set_ratio(self, ratio):
        self.fill.scale_x = 0.96 * max(0.0, ratio)


class Enemy(Entity):
    # ---- atributos padrao (sobrescritos pelas subclasses) ----
    NAME = 'Inimigo'
    MAX_HP = 10
    DAMAGE = 3
    SPEED = 3.0
    XP = 5
    COINS = (1, 2)
    RADIUS = 0.6
    AGGRO_RANGE = 11
    ATTACK_RANGE = 1.5
    WINDUP = 0.5          # tempo de aviso antes do golpe -> da para desviar!
    COOLDOWN = 1.3
    LEASH = 26            # distancia maxima que se afasta de casa
    STAGGER_TIME = 0.3    # tempo atordoado ao tomar golpe (0 = nao para)
    KNOCKBACK = 7
    HP_BAR_HEIGHT = 1.6
    NAME_COLOR = color.white
    dormant = False       # True quando esta longe do jogador (congelado, ver game._stream)

    def __init__(self, game, position, zone=None):
        super().__init__(position=Vec3(position.x, 0, position.z))
        self.game = game
        self.zone = zone
        self.home = Vec3(self.position)
        self.hp = self.MAX_HP
        self.dead = False
        self.state = 'wander'
        self.state_timer = random.uniform(0.5, 2)
        self.wander_target = None
        self.attack_cd = random.uniform(0.3, 1.0)
        self.knockback = Vec3(0, 0, 0)
        self.anim_t = random.uniform(0, 10)
        self.moving = False

        self.visual = Entity(parent=self)    # todas as pecas do corpo ficam aqui
        self.parts = []                      # (entidade, cor original) para piscar ao levar dano
        self.build()
        self.parts = [(e, e.color) for e in self.visual.get_descendants() if e.model]

        self.hp_bar = HealthBar3D(parent=self, y=self.HP_BAR_HEIGHT)

        # surge do chao
        self.visual.scale = 0.01
        self.visual.animate_scale(1, duration=0.5, curve=curve.out_back)

    # ----------------------------------------------------- para subclasses
    def build(self):
        part(parent=self.visual, scale=1, y=0.5, color=color.magenta)

    def animate_body(self, dt):
        pass

    def on_windup(self):
        """Aviso visual de que vai atacar."""
        self.visual.animate_scale(Vec3(1.15, 0.85, 1.15), duration=self.WINDUP * 0.8, curve=curve.out_quad)

    def on_attack(self):
        self.visual.animate_scale(Vec3(1, 1, 1), duration=0.15, curve=curve.out_back)

    # ---------------------------------------------------------------- IA
    @property
    def player(self):
        return self.game.player

    def face(self, target, dt, speed=10):
        d = target - self.position
        target_angle = math.degrees(math.atan2(d.x, d.z))
        self.rotation_y = lerp_angle(self.rotation_y, target_angle, min(1, dt * speed))

    def move_towards(self, target, speed, dt):
        d = Vec3(target.x - self.x, 0, target.z - self.z)
        if d.length() < 0.05:
            self.moving = False
            return
        self.position += d.normalized() * speed * dt
        self.face(target, dt)
        self.moving = True

    def player_reachable(self):
        p = self.player
        return (not p.dead and math.hypot(p.x, p.z) > VILLAGE_RADIUS
                and distance_xz(p.position, self.home) < self.LEASH + 6)

    def update(self):
        if self.dead:
            return
        dt = time.dt
        self.anim_t += dt
        self.moving = False
        self.attack_cd -= dt
        self.state_timer -= dt
        p = self.player
        dist = distance_xz(self.position, p.position)

        if self.state == 'wander':
            if dist < self.AGGRO_RANGE and self.player_reachable():
                self.set_state('chase')
            elif self.wander_target is not None:
                self.move_towards(self.wander_target, self.SPEED * 0.4, dt)
                if distance_xz(self.position, self.wander_target) < 0.5:
                    self.wander_target = None
                    self.state_timer = random.uniform(1.5, 4)
            elif self.state_timer <= 0:
                a = random.uniform(0, math.tau)
                r = random.uniform(2, 8)
                self.wander_target = self.home + Vec3(math.cos(a) * r, 0, math.sin(a) * r)

        elif self.state == 'chase':
            if not self.player_reachable() or dist > self.AGGRO_RANGE * 2.2:
                self.set_state('return')
            elif dist <= self.ATTACK_RANGE + p.RADIUS:
                self.face(p.position, dt)
                if self.attack_cd <= 0:
                    self.set_state('windup', self.WINDUP)
                    self.on_windup()
            else:
                self.move_towards(p.position, self.SPEED, dt)

        elif self.state == 'windup':
            self.face(p.position, dt, speed=4)
            if self.state_timer <= 0:
                self.on_attack()
                if dist <= self.ATTACK_RANGE + p.RADIUS + 0.5 and not p.dead:
                    p.take_damage(self.DAMAGE, self.position)
                self.attack_cd = self.COOLDOWN
                self.set_state('recover', 0.45)

        elif self.state in ('recover', 'stagger'):
            if self.state_timer <= 0:
                self.set_state('chase')

        elif self.state == 'return':
            self.move_towards(self.home, self.SPEED * 0.8, dt)
            self.hp = min(self.MAX_HP, self.hp + self.MAX_HP * 0.25 * dt)
            self.hp_bar.set_ratio(self.hp / self.MAX_HP)
            if distance_xz(self.position, self.home) < 1:
                self.hp_bar.enabled = self.hp < self.MAX_HP
                self.set_state('wander')
            elif dist < self.AGGRO_RANGE * 0.6 and self.player_reachable() and \
                    distance_xz(self.position, self.home) < self.LEASH * 0.7:
                self.set_state('chase')

        # empurrao (knockback) e colisoes
        if self.knockback.length() > 0.01:
            self.position += self.knockback * dt
            self.knockback = lerp(self.knockback, Vec3(0, 0, 0), min(1, dt * 8))
        self._separate()
        # nao entra na vila
        r = math.hypot(self.x, self.z)
        if r < VILLAGE_RADIUS + self.RADIUS:
            k = (VILLAGE_RADIUS + self.RADIUS) / max(r, 0.01)
            self.x *= k
            self.z *= k
        self.position = self.game.world.resolve_collision(self.position, self.RADIUS)

        self.animate_body(dt)

    def set_state(self, state, timer=0.0):
        self.state = state
        self.state_timer = timer
        if state == 'chase':
            self.hp_bar.enabled = True

    def _separate(self):
        """Evita que inimigos fiquem um dentro do outro."""
        for other in self.game.awake_enemies:
            if other is self or other.dead:
                continue
            dx, dz = self.x - other.x, self.z - other.z
            min_d = self.RADIUS + other.RADIUS
            d2 = dx * dx + dz * dz
            if 0.0001 < d2 < min_d * min_d:
                d = math.sqrt(d2)
                push = (min_d - d) * 0.5
                self.x += dx / d * push
                self.z += dz / d * push

    # ------------------------------------------------------------- combate
    def take_hit(self, damage, from_position, crit=False):
        if self.dead:
            return
        self.hp -= damage
        self.hp_bar.enabled = True
        self.hp_bar.set_ratio(self.hp / self.MAX_HP)

        FloatingText(self.position + Vec3(0, self.HP_BAR_HEIGHT + 0.3, 0),
                     f'{damage}!' if crit else str(damage),
                     text_color=color.rgb32(255, 220, 60) if crit else color.white,
                     scale=2.0 if crit else 1.5)

        away = Vec3(self.x - from_position.x, 0, self.z - from_position.z)
        if away.length() > 0.001:
            self.knockback = away.normalized() * self.KNOCKBACK * (1.4 if crit else 1)

        self._flash()
        if self.hp <= 0:
            self.die()
            return
        if self.STAGGER_TIME > 0:
            if self.state == 'windup':
                self.visual.animate_scale(1, duration=0.1)
            self.set_state('stagger', self.STAGGER_TIME)
        elif self.state in ('wander', 'return'):
            self.set_state('chase')

    def _flash(self):
        for e, _ in self.parts:
            e.color = color.white
        invoke(self._restore_colors, delay=0.08)

    def _restore_colors(self):
        if not self.dead:
            for e, c in self.parts:
                e.color = c

    def die(self):
        self.dead = True
        self.hp_bar.enabled = False
        sounds.enemy_die()
        self.game.on_enemy_killed(self)
        spawn_drops(self.game, self.position, random.randint(*self.COINS))
        for e, c in self.parts:
            e.color = c.tint(-0.3)
        self.visual.animate_scale(Vec3(1.3, 0.05, 1.3), duration=0.35, curve=curve.in_back)
        destroy_tree(self, delay=0.4)


# =============================================================== SLIME
class Slime(Enemy):
    NAME = 'Slime'
    MAX_HP = 16
    DAMAGE = 5
    SPEED = 2.6
    XP = 6
    COINS = (1, 3)
    RADIUS = 0.6
    AGGRO_RANGE = 9
    ATTACK_RANGE = 1.3
    WINDUP = 0.55
    COOLDOWN = 1.4
    HP_BAR_HEIGHT = 1.5
    COLORS = [color.rgb32(90, 210, 110), color.rgb32(80, 170, 230), color.rgb32(240, 120, 180)]

    def build(self):
        c = random.choice(self.COLORS)
        self.body = Entity(parent=self.visual)
        part(parent=self.body, scale=(1.1, 0.9, 1.1), y=0.45, color=c)
        part(parent=self.body, scale=(0.8, 0.25, 0.8), y=0.95, color=c.tint(0.1))
        part(parent=self.body, scale=(1.14, 0.2, 1.14), y=0.1, color=c.tint(-0.15))
        for sx in (-0.22, 0.22):
            part(parent=self.body, scale=(0.18, 0.24, 0.05), position=(sx, 0.6, 0.56), color=color.white)
            part(parent=self.body, scale=(0.09, 0.13, 0.05), position=(sx, 0.57, 0.58), color=color.black)
        part(parent=self.body, scale=(0.3, 0.06, 0.05), position=(0, 0.35, 0.56), color=c.tint(-0.35))

    def animate_body(self, dt):
        if self.state == 'windup':
            self.body.y = 0
            return
        hop_speed = 9 if self.moving else 3
        h = abs(math.sin(self.anim_t * hop_speed))
        self.body.y = h * (0.45 if self.moving else 0.06)
        self.body.scale = Vec3(1 + (1 - h) * 0.15, 1 - (1 - h) * 0.15, 1 + (1 - h) * 0.15)

    def on_windup(self):
        self.visual.animate_scale(Vec3(1.35, 0.65, 1.35), duration=self.WINDUP * 0.8, curve=curve.out_quad)

    def on_attack(self):
        # bote para frente
        self.visual.animate_scale(Vec3(0.85, 1.3, 0.85), duration=0.08)
        self.visual.animate_scale(Vec3(1, 1, 1), duration=0.25, delay=0.08, curve=curve.out_back)
        self.knockback = self.forward * 6


# =============================================================== GOBLIN
class Goblin(Enemy):
    NAME = 'Goblin'
    MAX_HP = 30
    DAMAGE = 8
    SPEED = 4.6
    XP = 14
    COINS = (3, 7)
    RADIUS = 0.5
    AGGRO_RANGE = 13
    ATTACK_RANGE = 1.5
    WINDUP = 0.4
    COOLDOWN = 1.0
    STAGGER_TIME = 0.25
    HP_BAR_HEIGHT = 1.75
    SKIN = color.rgb32(110, 170, 70)

    def build(self):
        skin, cloth = self.SKIN, color.rgb32(120, 84, 50)
        v = self.visual
        # pernas
        self.legs = []
        for sx in (-0.13, 0.13):
            pivot = Entity(parent=v, position=(sx, 0.55, 0))
            part(parent=pivot, scale=(0.17, 0.55, 0.19), y=-0.27, color=cloth.tint(-0.2))
            self.legs.append(pivot)
        part(parent=v, scale=(0.5, 0.5, 0.32), y=0.8, color=cloth)                          # tronco
        part(parent=v, scale=(0.52, 0.1, 0.34), y=0.6, color=color.rgb32(60, 40, 25))       # cinto
        self.head = Entity(parent=v, y=1.25)
        part(parent=self.head, scale=(0.5, 0.42, 0.42), color=skin)
        part(parent=self.head, scale=(0.1, 0.16, 0.12), position=(0, -0.04, 0.25), color=skin.tint(-0.1))  # nariz
        for sx in (-1, 1):
            part(parent=self.head, model='pyramid', scale=(0.12, 0.38, 0.08), position=(sx * 0.3, 0.02, 0),
                 rotation_z=-sx * 70, color=skin)                                            # orelhas
            part(parent=self.head, scale=(0.09, 0.07, 0.04), position=(sx * 0.12, 0.06, 0.21),
                 color=color.rgb32(255, 220, 40))                                            # olhos
        # bracos
        self.arms = []
        for sx in (-0.33, 0.33):
            pivot = Entity(parent=v, position=(sx, 1.0, 0))
            part(parent=pivot, scale=(0.14, 0.45, 0.15), y=-0.22, color=skin)
            self.arms.append(pivot)
        # porrete na mao direita
        club = Entity(parent=self.arms[1], y=-0.45, rotation_x=80)
        part(parent=club, scale=(0.08, 0.55, 0.08), y=0.2, color=color.rgb32(100, 70, 40))
        part(parent=club, scale=(0.18, 0.3, 0.18), y=0.55, color=color.rgb32(120, 85, 50))

    def animate_body(self, dt):
        if self.state == 'windup':
            self.arms[1].rotation_x = lerp(self.arms[1].rotation_x, -160, min(1, dt * 10))
            return
        swing = math.sin(self.anim_t * 14) * 40 if self.moving else 0
        self.legs[0].rotation_x = swing
        self.legs[1].rotation_x = -swing
        self.arms[0].rotation_x = -swing * 0.8
        if self.state != 'recover':
            self.arms[1].rotation_x = lerp(self.arms[1].rotation_x, swing * 0.5 - 20, min(1, dt * 10))
        self.visual.y = abs(math.sin(self.anim_t * 14)) * 0.08 if self.moving else 0

    def on_windup(self):
        pass   # o braco levantando e o aviso

    def on_attack(self):
        self.arms[1].animate('rotation_x', 10, duration=0.1, curve=curve.linear)


# ============================================================= ESQUELETO
class Skeleton(Enemy):
    NAME = 'Esqueleto'
    MAX_HP = 60
    DAMAGE = 14
    SPEED = 3.1
    XP = 30
    COINS = (6, 12)
    RADIUS = 0.55
    AGGRO_RANGE = 14
    ATTACK_RANGE = 1.9
    WINDUP = 0.75
    COOLDOWN = 1.6
    STAGGER_TIME = 0.0      # nao e interrompido pelos golpes!
    KNOCKBACK = 3
    HP_BAR_HEIGHT = 2.3
    BONE = color.rgb32(232, 228, 210)

    def build(self):
        bone = self.BONE
        v = self.visual
        self.legs = []
        for sx in (-0.15, 0.15):
            pivot = Entity(parent=v, position=(sx, 0.9, 0))
            part(parent=pivot, scale=(0.1, 0.85, 0.1), y=-0.43, color=bone)
            part(parent=pivot, scale=(0.16, 0.1, 0.26), position=(0, -0.85, 0.05), color=bone)
            self.legs.append(pivot)
        part(parent=v, scale=(0.45, 0.14, 0.24), y=0.95, color=bone)                 # bacia
        part(parent=v, scale=(0.1, 0.55, 0.1), y=1.25, color=bone)                   # coluna
        for i in range(3):                                                           # costelas
            part(parent=v, scale=(0.5 - i * 0.06, 0.06, 0.28), y=1.55 - i * 0.14, color=bone)
        self.head = Entity(parent=v, y=1.95)
        part(parent=self.head, scale=(0.42, 0.4, 0.42), color=bone)
        part(parent=self.head, scale=(0.32, 0.12, 0.3), position=(0, -0.22, 0.04), color=bone.tint(-0.08))
        for sx in (-0.1, 0.1):
            part(parent=self.head, scale=(0.11, 0.11, 0.04), position=(sx, 0.03, 0.21), color=color.black)
            self.eyes = part(parent=self.head, scale=(0.04, 0.04, 0.02), position=(sx, 0.03, 0.235),
                             color=color.rgb32(255, 60, 40), unlit=True)
        self.arms = []
        for sx in (-0.33, 0.33):
            pivot = Entity(parent=v, position=(sx, 1.62, 0))
            part(parent=pivot, scale=(0.09, 0.75, 0.09), y=-0.37, color=bone)
            self.arms.append(pivot)
        # espada enferrujada
        sword = Entity(parent=self.arms[1], y=-0.72, rotation_x=80)
        part(parent=sword, scale=(0.07, 0.25, 0.07), color=color.rgb32(70, 50, 40))
        part(parent=sword, scale=(0.3, 0.06, 0.08), y=0.14, color=color.rgb32(90, 80, 70))
        part(parent=sword, scale=(0.1, 1.0, 0.04), y=0.66, color=color.rgb32(150, 130, 115))
        # escudo velho no braco esquerdo
        part(parent=self.arms[0], scale=(0.08, 0.6, 0.5), position=(-0.08, -0.5, 0.1), color=color.rgb32(100, 80, 60))

    def animate_body(self, dt):
        if self.state == 'windup':
            self.arms[1].rotation_x = lerp(self.arms[1].rotation_x, -170, min(1, dt * 6))
            self.visual.rotation_y = lerp(self.visual.rotation_y, 25, min(1, dt * 6))
            return
        self.visual.rotation_y = lerp(self.visual.rotation_y, 0, min(1, dt * 8))
        swing = math.sin(self.anim_t * 9) * 30 if self.moving else 0
        self.legs[0].rotation_x = swing
        self.legs[1].rotation_x = -swing
        self.arms[0].rotation_x = -swing * 0.6 - 30
        if self.state != 'recover':
            self.arms[1].rotation_x = lerp(self.arms[1].rotation_x, swing * 0.4 - 15, min(1, dt * 6))
        # balancinho macabro da cabeca
        self.head.rotation_z = math.sin(self.anim_t * 3) * 6

    def on_windup(self):
        pass

    def on_attack(self):
        self.arms[1].animate('rotation_x', 15, duration=0.12, curve=curve.linear)
        self.visual.animate('rotation_y', -20, duration=0.12, curve=curve.linear)
