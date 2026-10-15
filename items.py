"""Moedas que caem dos inimigos. (Pocoes NAO caem de monstros: so a bruxa vende.)"""
import math
import random

from ursina import Entity, Vec3, color, distance, time

from models import destroy_tree, part
import sounds

GOLD = color.rgb32(255, 200, 40)


class Coin(Entity):
    MAGNET_RANGE = 3.5
    COLLECT_RANGE = 0.9
    LIFETIME = 60
    dormant = False

    def __init__(self, game, position, value=1):
        super().__init__(position=Vec3(position) + Vec3(0, 0.6, 0))
        self.game = game
        self.value = value
        self.age = 0
        self.landed = False
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1.5, 3.5)
        self.velocity = Vec3(math.cos(angle) * speed, random.uniform(5, 7), math.sin(angle) * speed)
        self.visual = Entity(parent=self)
        part('cylinder', parent=self.visual, scale=(0.42, 0.08, 0.42), rotation_x=90, z=-0.04, color=GOLD)
        part('cylinder', parent=self.visual, scale=(0.3, 0.1, 0.3), rotation_x=90, z=-0.05, color=GOLD.tint(0.15))
        game.pickups.append(self)

    def update(self):
        dt = time.dt
        self.age += dt
        player = self.game.player

        if not self.landed:
            self.velocity.y -= 22 * dt
            self.position += self.velocity * dt
            if self.y <= 0.35:
                self.y = 0.35
                self.landed = True
            return

        self.visual.rotation_y += 140 * dt
        self.visual.y = math.sin(self.age * 4) * 0.08

        if not player.dead:
            target = player.position + Vec3(0, 0.9, 0)
            d = distance(self.position, target)
            if d < self.MAGNET_RANGE:
                self.position += (target - self.position).normalized() * dt * (6 + (self.MAGNET_RANGE - d) * 5)
            if d < self.COLLECT_RANGE:
                player.add_coins(self.value)
                sounds.coin()
                self.remove()
                return

        if self.age > self.LIFETIME:
            self.remove()
        elif self.age > self.LIFETIME - 5:
            self.visual.enabled = int(self.age * 8) % 2 == 0   # pisca antes de sumir

    def remove(self):
        if self in self.game.pickups:
            self.game.pickups.remove(self)
        destroy_tree(self)


def spawn_drops(game, position, coins):
    """Espalha moedas em ate 5 pilhas."""
    piles = min(coins, 5)
    for i in range(piles):
        value = coins // piles + (1 if i < coins % piles else 0)
        Coin(game, position, value)
