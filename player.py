"""O heroi: movimento em terceira pessoa, camera, combate, ferramentas, inventario e fome."""
import math
import random

from ursina import (Entity, Vec3, camera, color, curve, destroy, held_keys, invoke, lerp, lerp_angle, mouse, time)

from catalog import AXE, FOOD, ITEMS, PICKAXE, POTION, SCYTHE, TOOL, TOOL_ITEM
from inventory import Inventory
from models import destroy_tree, part, flat
from settings import (C, CAMERA_DISTANCE, CAMERA_HEIGHT, CAMERA_MAX_DISTANCE, CAMERA_MIN_DISTANCE,
                      CRIT_CHANCE, CRIT_MULTIPLIER, DAMAGE_PER_LEVEL, GRAVITY, HP_PER_LEVEL,
                      HUNGER_DRAIN, HUNGER_SPRINT_MULT, MAX_HUNGER, MOUSE_SENSITIVITY, PLAYER_JUMP_SPEED,
                      PLAYER_SPAWN, PLAYER_SPAWN_YAW, PLAYER_SPEED, PLAYER_SPRINT_SPEED, PLAYER_START_HP,
                      START_COINS, STARVING_DAMAGE, WELL_FED_REGEN, WELL_FED_THRESHOLD, xp_for_level)
from ui import FloatingText
from weapons import build_held
import sounds

# Poses do braco direito durante o golpe (rotation_x do ombro)
ARM_IDLE = -25
ARM_RAISED = -175
ARM_STRIKE = -5

GAIN_COLOR = color.rgb32(170, 230, 140)


class Player(Entity):
    RADIUS = 0.45

    def __init__(self, game):
        super().__init__(position=PLAYER_SPAWN, rotation_y=PLAYER_SPAWN_YAW)
        self.game = game

        # ---- atributos de RPG ----
        self.level = 1
        self.xp = 0
        self.xp_next = xp_for_level(1)
        self.max_hp = PLAYER_START_HP
        self.hp = self.max_hp
        self.hunger = MAX_HUNGER
        self.coins = START_COINS
        self.kills = 0

        # ---- inventario: comeca so com a espada de madeira ----
        self.inventory = Inventory()
        self.inventory.add('espada_madeira')
        self.inventory.on_change = lambda: self.game.hud.refresh(self)
        self.equipped = ITEMS['espada_madeira']

        # ---- estado fisico ----
        self.velocity_y = 0.0
        self.grounded = True
        self.knockback = Vec3(0, 0, 0)
        self.invulnerable = 0.0
        self.dead = False
        self.walk_t = 0.0
        self._starve_tick = 0.0

        # ---- ataque ----
        self.attacking = False
        self.attack_t = 0.0
        self.hit_done = False

        self._build_body()

        # ---- camera em terceira pessoa ----
        self.cam_pivot = Entity(position=self.position + Vec3(0, CAMERA_HEIGHT, 0), rotation=(18, PLAYER_SPAWN_YAW, 0))
        self.cam_distance = CAMERA_DISTANCE
        self.mouse_grace = 0.4       # segundos ignorando o mouse (apos travar o cursor)
        camera.parent = self.cam_pivot
        camera.position = (0, 0, -self.cam_distance)
        camera.rotation = (0, 0, 0)
        camera.fov = 70

    # ================================================================ corpo
    def _build_body(self):
        self.body = Entity(parent=self)
        b = self.body
        # pernas (pivo no quadril para animar a caminhada)
        self.legs = []
        for sx in (-0.15, 0.15):
            pivot = Entity(parent=b, position=(sx, 0.85, 0))
            part(parent=pivot, scale=(0.22, 0.6, 0.24), y=-0.3, color=C['pants'])
            part(parent=pivot, scale=(0.24, 0.25, 0.3), position=(0, -0.72, 0.03), color=C['boots'])
            self.legs.append(pivot)
        # tronco
        part(parent=b, scale=(0.58, 0.62, 0.34), y=1.17, color=C['tunic'])
        part(parent=b, scale=(0.6, 0.12, 0.36), y=0.9, color=C['belt'])
        part(parent=b, scale=(0.12, 0.1, 0.04), position=(0, 0.9, 0.18), color=color.rgb32(220, 190, 80))  # fivela
        part(parent=b, scale=(0.62, 0.2, 0.36), y=0.78, color=C['tunic'].tint(-0.1))                       # saia da tunica
        # cabeca
        self.head = Entity(parent=b, y=1.72)
        part(parent=self.head, scale=(0.42, 0.42, 0.42), color=C['skin'])
        part(parent=self.head, scale=(0.46, 0.14, 0.46), y=0.2, color=C['hair'])
        part(parent=self.head, scale=(0.46, 0.3, 0.12), position=(0, 0.06, -0.18), color=C['hair'])
        for sx in (-0.09, 0.09):
            part(parent=self.head, scale=(0.07, 0.09, 0.03), position=(sx, 0.02, 0.21), color=color.rgb32(30, 30, 40))
        # capa
        self.cape = Entity(parent=b, position=(0, 1.45, -0.18))
        part(parent=self.cape, scale=(0.56, 0.85, 0.05), y=-0.42, color=color.rgb32(170, 40, 40))
        # bracos (pivo no ombro)
        self.left_arm = Entity(parent=b, position=(-0.38, 1.42, 0))
        part(parent=self.left_arm, scale=(0.17, 0.55, 0.19), y=-0.26, color=C['tunic'].tint(-0.05))
        part(parent=self.left_arm, scale=(0.15, 0.12, 0.17), y=-0.58, color=C['skin'])
        self.right_arm = Entity(parent=b, position=(0.38, 1.42, 0), rotation_x=ARM_IDLE)
        part(parent=self.right_arm, scale=(0.17, 0.55, 0.19), y=-0.26, color=C['tunic'].tint(-0.05))
        part(parent=self.right_arm, scale=(0.15, 0.12, 0.17), y=-0.58, color=C['skin'])
        # o item equipado fica na mao direita, apontando para frente
        self.hand = Entity(parent=self.right_arm, y=-0.6, rotation_x=90)
        self.held = build_held(self.hand, self.equipped)

        # sombra fake sob os pes (ajuda a ver onde vai cair no pulo)
        self.blob = flat('circle', parent=self, rotation_x=90, y=0.03, scale=0.9,
                         color=color.rgba(0, 0, 0, 0.25))
        self._collect_parts()

    def _collect_parts(self):
        """Pecas do corpo (para piscar em vermelho ao levar dano)."""
        self.parts = [(e, e.color) for e in self.body.get_descendants() if e.model]

    # ============================================================ atributos
    def _base_damage(self):
        return self.equipped.damage + (self.level - 1) * DAMAGE_PER_LEVEL

    def attack_damage_range(self):
        base = self._base_damage()
        return f'{base - 1}-{base + 1}'

    def roll_damage(self):
        base = self._base_damage()
        dmg = random.randint(base - 1, base + 1)
        crit = random.random() < CRIT_CHANCE
        if crit:
            dmg = int(dmg * CRIT_MULTIPLIER)
        return max(1, dmg), crit

    def gain_xp(self, amount):
        self.xp += amount
        FloatingText(self.position + Vec3(0, 2.4, 0), f'+{amount} XP', text_color=color.rgb32(120, 190, 255),
                     scale=1.2, lifetime=1.2)
        while self.xp >= self.xp_next:
            self.xp -= self.xp_next
            self.level += 1
            self.xp_next = xp_for_level(self.level)
            self.max_hp += HP_PER_LEVEL
            self.hp = self.max_hp
            sounds.level_up()
            self.game.hud.show_message(f'NÍVEL {self.level}!',
                                       f'Vida máxima +{HP_PER_LEVEL}   Dano +{DAMAGE_PER_LEVEL}   Vida restaurada',
                                       text_color=color.rgb32(255, 220, 90))
            self._level_up_effect()
        self.game.hud.refresh(self)

    def _level_up_effect(self):
        ring = flat('quad', texture='circle_hollow', position=self.position + Vec3(0, 0.1, 0), rotation_x=90,
                    scale=0.5, color=color.rgba(1, 0.9, 0.3, 0.9))
        ring.animate_scale(6, duration=0.7, curve=curve.out_expo)
        ring.animate_color(color.rgba(1, 0.9, 0.3, 0), duration=0.7)
        destroy(ring, delay=0.75)

    # ============================================================== dinheiro
    def add_coins(self, amount):
        self.coins += amount
        self.game.hud.refresh(self)

    def spend_coins(self, amount):
        if self.coins < amount:
            return False
        self.coins -= amount
        self.game.hud.refresh(self)
        return True

    # =========================================================== equipamento
    def equip(self, item_id, silent=False):
        if not self.inventory.has(item_id) or not ITEMS[item_id].equippable:
            return False
        if self.equipped.id == item_id:
            return True
        self.equipped = ITEMS[item_id]
        destroy_tree(self.held)
        self.held = build_held(self.hand, self.equipped)
        self._collect_parts()
        self.held.scale = 0.01
        self.held.animate_scale(1, duration=0.2, curve=curve.out_back)
        self.game.hud.refresh(self)
        if not silent:
            self.game.hud.notify(f'Equipado: {self.equipped.name}')
        return True

    def equip_slot(self, index):
        slots = self.inventory.equippables()
        if 0 <= index < len(slots) and not self.attacking:
            self.equip(slots[index].id)

    # ============================================================ consumo
    def consume(self, item_id):
        """Come um alimento ou bebe uma pocao do inventario."""
        it = ITEMS[item_id]
        if not it.consumable or not self.inventory.has(item_id) or self.dead:
            return False
        heal = it.heal + int(self.max_hp * it.heal_ratio)
        if it.kind == FOOD and self.hunger >= MAX_HUNGER and self.hp >= self.max_hp:
            self.game.hud.notify('Você está satisfeito.')
            return False
        if it.kind == POTION and self.hp >= self.max_hp:
            self.game.hud.notify('Sua vida já está cheia.')
            return False
        self.inventory.remove(item_id)
        healed = min(heal, self.max_hp - int(self.hp))
        self.hp = min(self.max_hp, self.hp + heal)
        self.hunger = min(MAX_HUNGER, self.hunger + it.hunger)
        if it.kind == FOOD:
            sounds.eat()
        else:
            sounds.potion()
        y = 2.2
        if healed > 0:
            FloatingText(self.position + Vec3(0, y, 0), f'+{healed} vida', text_color=color.rgb32(110, 240, 110),
                         scale=1.4)
            y += 0.4
        if it.hunger:
            FloatingText(self.position + Vec3(0, y, 0), f'+{it.hunger} fome', text_color=color.rgb32(255, 180, 80),
                         scale=1.2)
        self.game.hud.refresh(self)
        return True

    def drink_potion(self):
        for pid in ('pocao_vida', 'pocao_grande'):
            if self.inventory.has(pid):
                return self.consume(pid)
        self.game.hud.notify('Você não tem poções. Compre na loja de Bruxaria.')
        return False

    def eat_food(self):
        foods = self.inventory.items_of(FOOD)
        if not foods:
            self.game.hud.notify('Você não tem comida. Compre na loja de Alimentos.')
            return False
        # escolhe o alimento que mais enche sem desperdicar muito
        missing = MAX_HUNGER - self.hunger
        best = min(foods, key=lambda f: abs(missing - f.hunger))
        return self.consume(best.id)

    def receive(self, gained):
        """Adiciona itens coletados ao inventario, com textos flutuantes."""
        y = 2.2
        for item_id, amount in gained.items():
            added = self.inventory.add(item_id, amount)
            if added:
                FloatingText(self.position + Vec3(0, y, 0), f'+{added} {ITEMS[item_id].name}',
                             text_color=GAIN_COLOR, scale=1.2, lifetime=1.2)
                y += 0.4

    # ================================================================ dano
    def take_damage(self, amount, from_position=None, silent=False):
        if self.dead or (self.invulnerable > 0 and not silent):
            return
        self.hp -= amount
        if not silent:
            self.invulnerable = 0.6
            sounds.hurt()
            FloatingText(self.position + Vec3(0, 2.2, 0), f'-{amount}', text_color=color.rgb32(255, 80, 80), scale=1.6)
            if from_position is not None:
                away = Vec3(self.x - from_position.x, 0, self.z - from_position.z)
                if away.length() > 0.001:
                    self.knockback = away.normalized() * 9
            for e, _ in self.parts:
                e.color = color.rgb32(255, 90, 90)
            invoke(self._restore_colors, delay=0.12)
            self.game.hud.flash_damage()
            camera.shake(duration=0.2, magnitude=0.6)
        if self.hp <= 0:
            self.hp = 0
            self.die()
        self.game.hud.refresh(self)

    def _restore_colors(self):
        for e, c in self.parts:
            if e:
                e.color = c

    def die(self):
        self.dead = True
        self.attacking = False
        self.body.animate('rotation_x', -90, duration=0.6, curve=curve.out_bounce)
        self.body.animate('y', 0.2, duration=0.6)
        self.game.on_player_died()

    def respawn(self):
        self.dead = False
        self.hp = self.max_hp
        self.hunger = max(self.hunger, MAX_HUNGER * 0.5)
        self.position = PLAYER_SPAWN
        self.rotation_y = PLAYER_SPAWN_YAW
        self.cam_pivot.rotation_y = PLAYER_SPAWN_YAW
        self.body.rotation_x = 0
        self.body.y = 0
        self.knockback = Vec3(0, 0, 0)
        self.velocity_y = 0
        self.invulnerable = 2.0
        self._restore_colors()
        self.game.hud.refresh(self)

    # =============================================================== fome
    def _update_hunger(self, dt, sprinting):
        drain = HUNGER_DRAIN * (HUNGER_SPRINT_MULT if sprinting else 1)
        before = self.hunger
        self.hunger = max(0.0, self.hunger - drain * dt)
        if before > 25 >= self.hunger:
            self.game.hud.notify('Você está com fome! Coma algo (tecla C).')
        if self.hunger <= 0:
            self._starve_tick += dt
            if self._starve_tick >= 1.0:
                self._starve_tick = 0
                self.take_damage(round(STARVING_DAMAGE), silent=True)
                self.game.hud.flash_damage()
        elif self.hunger >= WELL_FED_THRESHOLD and self.hp < self.max_hp:
            self.hp = min(self.max_hp, self.hp + self.max_hp * WELL_FED_REGEN * dt)

    # =============================================================== ataque
    def start_attack(self):
        if self.attacking or self.dead:
            return
        self.attacking = True
        self.attack_t = 0.0
        self.hit_done = False
        # vira na direcao da camera para mirar onde voce esta olhando
        self.rotation_y = self.cam_pivot.rotation_y
        sounds.swing()

    def _update_attack(self, dt):
        self.attack_t += dt
        p = self.attack_t / self.equipped.swing_time
        if p < 0.35:      # levanta o item
            k = curve.out_quad(p / 0.35)
            self.right_arm.rotation_x = lerp(ARM_IDLE, ARM_RAISED, k)
        elif p < 0.55:    # golpe!
            k = curve.in_quad((p - 0.35) / 0.2)
            self.right_arm.rotation_x = lerp(ARM_RAISED, ARM_STRIKE, k)
            self.position += self.forward * dt * 3   # pequeno avanco
        else:             # volta
            k = curve.out_quad(min(1, (p - 0.55) / 0.45))
            self.right_arm.rotation_x = lerp(ARM_STRIKE, ARM_IDLE, k)

        if not self.hit_done and p >= 0.48:
            self.hit_done = True
            self._deal_hits()
        if p >= 1:
            self.attacking = False
            self.right_arm.rotation_x = ARM_IDLE

    def _in_front(self, x, z, max_dist):
        to = Vec3(x - self.x, 0, z - self.z)
        dist = to.length()
        if dist > max_dist:
            return False
        return dist < 0.8 or to.normalized().dot(self.forward) >= 0.35   # cone de ~140 graus a frente

    def _deal_hits(self):
        reach = self.equipped.reach
        hit_any = False
        for enemy in list(self.game.awake_enemies):
            if enemy.dead or not self._in_front(enemy.x, enemy.z, reach + enemy.RADIUS):
                continue
            dmg, crit = self.roll_damage()
            enemy.take_hit(dmg, self.position, crit)
            hit_any = True
            if crit:
                sounds.crit()
        if hit_any:
            sounds.hit()
            self._slash_effect(color.rgba(1, 1, 1, 0.6))
            return
        self._hit_resource(reach)

    def _hit_resource(self, reach):
        """Golpeia a arvore/pedra/planta mais proxima a frente."""
        candidates = [n for n in self.game.world.nodes
                      if not n.depleted and self._in_front(n.x, n.z, reach + n.radius)]
        if not candidates:
            return
        node = min(candidates, key=lambda n: (n.x - self.x) ** 2 + (n.z - self.z) ** 2)
        if self.equipped.kind != TOOL or self.equipped.tool != node.tool:
            self.game.hud.notify(f'{node.label}: use a {ITEMS[TOOL_ITEM[node.tool]].name}.')
            return
        gained = node.hit()
        {AXE: sounds.chop, PICKAXE: sounds.mine, SCYTHE: sounds.harvest}[node.tool]()
        self.receive(gained)

    def _slash_effect(self, c):
        slash = flat('quad', position=self.position + self.forward * 1.4 + Vec3(0, 1.1, 0),
                     rotation=(0, self.rotation_y, 45), scale=(0.15, 2.0), color=c, double_sided=True)
        slash.animate_scale((0.02, 2.6), duration=0.15)
        slash.animate_color(color.rgba(1, 1, 1, 0), duration=0.15)
        destroy(slash, delay=0.2)

    # ================================================================ input
    def input(self, key):
        if self.dead or self.game.blocked:
            return
        if key == 'left mouse down':
            if self.mouse_grace <= 0:     # o clique que fecha um menu/trava o mouse nao vira ataque
                self.start_attack()
        elif key == 'space' and self.grounded:
            self.velocity_y = PLAYER_JUMP_SPEED
            self.grounded = False
            sounds.jump()
        elif key == 'e':
            self.drink_potion()
        elif key == 'c':
            self.eat_food()
        elif key in '123456789' and len(key) == 1:
            self.equip_slot(int(key) - 1)
        elif key == 'scroll up':
            self.cam_distance = max(CAMERA_MIN_DISTANCE, self.cam_distance - 1)
        elif key == 'scroll down':
            self.cam_distance = min(CAMERA_MAX_DISTANCE, self.cam_distance + 1)

    # =============================================================== update
    def update(self):
        if self.game.cutscene:      # durante cenas, a cutscene controla o heroi e a camera
            return
        dt = time.dt
        self._update_camera(dt)
        if self.dead:
            return

        self.invulnerable = max(0.0, self.invulnerable - dt)

        # ---- movimento relativo a camera ----
        yaw = math.radians(self.cam_pivot.rotation_y)
        forward = Vec3(math.sin(yaw), 0, math.cos(yaw))
        right = Vec3(math.cos(yaw), 0, -math.sin(yaw))
        move = forward * (held_keys['w'] - held_keys['s']) + right * (held_keys['d'] - held_keys['a'])
        moving = move.length() > 0.01
        # com fome zerada nao da para correr
        sprinting = held_keys['shift'] and moving and not self.attacking and self.hunger > 0
        speed = PLAYER_SPRINT_SPEED if sprinting else PLAYER_SPEED
        if self.attacking:
            speed *= 0.45

        if moving:
            move = move.normalized()
            self.position += move * speed * dt
            if not self.attacking:
                target = math.degrees(math.atan2(move.x, move.z))
                self.rotation_y = lerp_angle(self.rotation_y, target, min(1, dt * 14))

        # ---- empurrao ----
        if self.knockback.length() > 0.01:
            self.position += self.knockback * dt
            self.knockback = lerp(self.knockback, Vec3(0, 0, 0), min(1, dt * 9))

        # ---- pulo / gravidade ----
        self.velocity_y -= GRAVITY * dt
        self.y += self.velocity_y * dt
        if self.y <= 0:
            self.y = 0
            self.velocity_y = 0
            self.grounded = True
        self.blob.y = 0.03 - self.y
        self.blob.scale = max(0.4, 0.9 - self.y * 0.15)

        # ---- colisao com o mundo ----
        self.position = self.game.world.resolve_collision(self.position, self.RADIUS)

        self._update_hunger(dt, sprinting)

        # ---- animacoes ----
        if self.attacking:
            self._update_attack(dt)
        self._animate_walk(dt, moving, sprinting)

    def _animate_walk(self, dt, moving, sprinting):
        if moving and self.grounded:
            self.walk_t += dt * (13 if sprinting else 9)
            swing = math.sin(self.walk_t) * (45 if sprinting else 32)
            self.body.y = abs(math.sin(self.walk_t)) * 0.06
        else:
            swing = lerp(self.legs[0].rotation_x, 0, min(1, dt * 10))
            self.body.y = lerp(self.body.y, 0, min(1, dt * 10))
        if not self.grounded:
            swing = 25
        self.legs[0].rotation_x = swing
        self.legs[1].rotation_x = -swing
        self.left_arm.rotation_x = -swing * 0.8
        if not self.attacking:
            self.right_arm.rotation_x = ARM_IDLE + swing * 0.3
        # a capa balanca com o movimento
        target_cape = 25 if (moving and sprinting) else (12 if moving else 3)
        self.cape.rotation_x = lerp(self.cape.rotation_x, target_cape + math.sin(time.time() * 6) * 3, min(1, dt * 6))

    def _update_camera(self, dt):
        self.mouse_grace = max(0.0, self.mouse_grace - dt)
        # ignora o "salto" do cursor logo apos travar o mouse (mouse_grace).
        # Movimentos rapidos NAO sao descartados: com o mouse travado, velocity e a distancia
        # do cursor ate o centro da tela, entao um giro rapido gera valores grandes legitimos.
        if mouse.locked and not self.game.blocked and self.mouse_grace <= 0:
            self.cam_pivot.rotation_y += mouse.velocity[0] * MOUSE_SENSITIVITY
            self.cam_pivot.rotation_x -= mouse.velocity[1] * MOUSE_SENSITIVITY
            self.cam_pivot.rotation_x = max(-10, min(65, self.cam_pivot.rotation_x))
        target = self.position + Vec3(0, CAMERA_HEIGHT, 0)
        self.cam_pivot.position = lerp(self.cam_pivot.position, target, min(1, dt * 12))
        distance = self.camera_clearance(self.cam_distance)
        # aproxima rapido (para nao atravessar a parede) e se afasta devagar
        speed = 20 if distance < -camera.z else 6
        camera.z = lerp(camera.z, -distance, min(1, dt * speed))

    def camera_clearance(self, desired):
        """Distancia maxima da camera sem atravessar casas, barracas e tendas.

        Lanca um raio (no plano do chao) do heroi para tras e encurta a distancia
        se ele bater num obstaculo grande. Arvores finas sao ignoradas (a camera
        ficaria pulando ao passar pela floresta).
        """
        pivot = self.cam_pivot
        back = -pivot.forward
        horizontal = math.hypot(back.x, back.z)
        if horizontal < 0.05:            # olhando reto para baixo: nada no caminho
            return desired
        dx, dz = back.x / horizontal, back.z / horizontal
        ox, oz = pivot.x, pivot.z
        reach = desired * horizontal       # quanto a camera anda no plano do chao
        best = reach
        for o in self.game.world.obstacles:
            if not o.active or o.r < 1.0:
                continue
            fx, fz = o.x - ox, o.z - oz
            if fx * fx + fz * fz > (reach + o.r + 1) ** 2:
                continue
            r = o.r + 0.35
            along = fx * dx + fz * dz                     # projecao do centro no raio
            side2 = fx * fx + fz * fz - along * along     # distancia ao raio, ao quadrado
            if side2 >= r * r or along < 0:
                continue
            hit = along - math.sqrt(r * r - side2)        # onde o raio entra no circulo
            best = min(best, max(1.2, hit))
        return min(desired, best / horizontal)
