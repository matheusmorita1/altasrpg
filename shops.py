"""As lojas da vila: dados de cada loja e os vendedores (NPCs)."""
import math
from dataclasses import dataclass, field

from ursina import Entity, color, lerp_angle, time

from models import part
from settings import C
from world import SHOP_SPOTS, facing_center


@dataclass
class Shop:
    kind: str
    title: str
    vendor: str
    greeting: str
    stock: list = field(default_factory=list)   # ids de itens a venda
    crafting: bool = False                       # ferraria tambem fabrica armas


SHOPS = {
    'food': Shop('food', 'Quitanda da Dona Flora', 'Dona Flora',
                 'Frutas fresquinhas! Cada uma cura um pouco e mata a fome.',
                 ['maca', 'banana', 'uvas', 'pera']),
    'smith': Shop('smith', 'Ferraria do Bruno', 'Bruno, o ferreiro',
                  'Ferramentas para o trabalho duro. Traga madeira e pedra que eu forjo armas melhores!',
                  ['picareta', 'machado', 'foice'], crafting=True),
    'witch': Shop('witch', 'Cabana da Bruxa Morgana', 'Morgana',
                  'Hehehe... poções de vida, preparadas com ervas raras. Os monstros não as têm!',
                  ['pocao_vida', 'pocao_grande']),
}

INTERACT_DISTANCE = 4.2


class ShopNPC(Entity):
    """Vendedor atras do balcao. Vira para o jogador quando ele chega perto."""

    def __init__(self, game, shop):
        x, z = SHOP_SPOTS[shop.kind]
        self.base_yaw = facing_center(x, z)
        yaw = math.radians(self.base_yaw)
        # fica atras do balcao (o balcao fica na frente da barraca)
        super().__init__(position=(x - math.sin(yaw) * 0.55, 0, z - math.cos(yaw) * 0.55),
                         rotation_y=self.base_yaw)
        self.stall_x, self.stall_z = x, z
        self.game = game
        self.shop = shop
        self.t = 0.0
        self.body = Entity(parent=self)
        {'food': self._build_grocer, 'smith': self._build_smith, 'witch': self._build_witch}[shop.kind]()

    # ------------------------------------------------------------ modelos
    def _humanoid(self, shirt, pants, skin=C['skin']):
        b = self.body
        for sx in (-0.14, 0.14):
            part(parent=b, scale=(0.2, 0.8, 0.22), position=(sx, 0.4, 0), color=pants)
        part(parent=b, scale=(0.58, 0.65, 0.34), y=1.12, color=shirt)
        for sx in (-0.37, 0.37):
            part(parent=b, scale=(0.16, 0.6, 0.18), position=(sx, 1.12, 0), color=shirt.tint(-0.08))
            part(parent=b, scale=(0.14, 0.12, 0.16), position=(sx, 0.77, 0), color=skin)
        self.head = Entity(parent=b, y=1.68)
        part(parent=self.head, scale=0.42, color=skin)
        for sx in (-0.09, 0.09):
            part(parent=self.head, scale=(0.07, 0.08, 0.03), position=(sx, 0.02, 0.21), color=color.rgb32(30, 30, 40))
        return self.head

    def _build_grocer(self):
        head = self._humanoid(color.rgb32(230, 200, 160), color.rgb32(90, 70, 50))
        part(parent=self.body, scale=(0.5, 0.6, 0.05), position=(0, 0.95, 0.18), color=color.rgb32(90, 160, 80))  # avental
        part(parent=head, scale=(0.46, 0.12, 0.46), y=0.2, color=color.rgb32(170, 120, 80))       # cabelo
        part('cylinder', parent=head, scale=(0.9, 0.05, 0.9), y=0.25, color=color.rgb32(230, 200, 110))   # chapeu
        part('cylinder', parent=head, scale=(0.45, 0.22, 0.45), y=0.25, color=color.rgb32(230, 200, 110))

    def _build_smith(self):
        head = self._humanoid(color.rgb32(150, 70, 50), color.rgb32(60, 50, 45), skin=color.rgb32(220, 170, 130))
        part(parent=self.body, scale=(0.56, 0.75, 0.05), position=(0, 0.9, 0.18), color=color.rgb32(80, 55, 35))  # avental de couro
        part(parent=head, scale=(0.36, 0.22, 0.1), position=(0, -0.17, 0.18), color=color.rgb32(110, 60, 30))  # barba
        part(parent=head, scale=(0.44, 0.06, 0.44), y=0.22, color=color.rgb32(220, 170, 130).tint(-0.1))       # careca

    def _build_witch(self):
        robe = color.rgb32(90, 45, 130)
        head = self._humanoid(robe, robe, skin=color.rgb32(190, 220, 160))
        part(parent=self.body, scale=(0.7, 0.9, 0.45), y=0.45, color=robe.tint(-0.1))           # saia longa
        part(parent=head, scale=(0.46, 0.4, 0.12), position=(0, -0.05, -0.19), color=color.rgb32(40, 30, 40))  # cabelo
        part('cylinder', parent=head, scale=(1.0, 0.05, 1.0), y=0.2, color=color.rgb32(40, 30, 50))  # aba do chapeu
        part('cone', parent=head, scale=(0.55, 0.85, 0.55), y=0.22, rotation_z=8, color=color.rgb32(40, 30, 50))
        part(parent=head, scale=(0.07, 0.14, 0.08), position=(0, -0.04, 0.24), color=color.rgb32(170, 200, 140))  # nariz

    # ---------------------------------------------------------- animacao
    def distance_to_player(self):
        p = self.game.player
        return math.hypot(p.x - self.stall_x, p.z - self.stall_z)

    def update(self):
        self.t += time.dt
        self.body.y = math.sin(self.t * 2.2) * 0.02
        p = self.game.player
        if self.distance_to_player() < 7:
            target = math.degrees(math.atan2(p.x - self.x, p.z - self.z))
        else:
            target = self.base_yaw
        self.rotation_y = lerp_angle(self.rotation_y, target, min(1, time.dt * 5))
