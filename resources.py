"""Recursos coletaveis: arvores (machado), pedras (picareta) e plantas (foice).

Cada recurso aguenta alguns golpes, da materiais a cada golpe e, quando acaba,
some e volta a crescer depois de um tempo.

Desempenho: os recursos NAO sao Entities separadas. Eles sao agrupados em
"chunks" (pedacos do mapa) e cada chunk e uma malha unica. Quando um recurso
some ou renasce, so o chunk dele e reconstruido; a animacao e feita por uma
copia temporaria ("fantasma").
"""
import math
import random

from ursina import Entity, Mesh, Vec3, color, curve, destroy, invoke, time

from catalog import AXE, PICKAXE, SCYTHE
from models import SHADER, part
from settings import C


# ------------------------------------------------------------- modelos 3D
def add_tree(batch, rng, x=0.0, z=0.0, scale=1.0):
    trunk_h = 1.6 * scale
    batch.add('cylinder6', position=(x, 0, z), scale=(0.45 * scale, trunk_h, 0.45 * scale), color=C['trunk'])
    if rng.random() < 0.55:   # pinheiro
        leaf = rng.choice([C['leaves'], C['leaves_dark']])
        for i, (r, h) in enumerate([(2.6, 2.2), (2.0, 1.9), (1.3, 1.6)]):
            batch.add('cone', position=(x, trunk_h * 0.7 + i * 1.1 * scale, z),
                      scale=(r * scale, h * scale, r * scale), rotation_y=rng.uniform(0, 60), color=leaf)
    else:   # arvore redonda
        leaf = rng.choice([C['leaves'], C['leaves_light']])
        batch.add('icosphere', position=(x, trunk_h + 1.0 * scale, z), scale=2.6 * scale, color=leaf)
        batch.add('icosphere', position=(x + 0.6 * scale, trunk_h + 1.7 * scale, z - 0.3 * scale),
                  scale=1.7 * scale, color=leaf.tint(0.06))


def add_rock(batch, rng, x=0.0, z=0.0, s=1.0):
    base = rng.choice([C['rock'], C['rock_dark']])
    batch.add('icosphere', position=(x, s * 0.25, z), scale=(s * 1.3, s, s * 1.1),
              rotation_y=rng.uniform(0, 360), color=base)
    # pedrinhas em volta
    for _ in range(2):
        a = rng.uniform(0, math.tau)
        batch.add('gem', position=(x + math.cos(a) * s * 0.75, 0.1, z + math.sin(a) * s * 0.75),
                  scale=s * 0.3, rotation_y=rng.uniform(0, 360), color=base.tint(-0.08))


HERB_FLOWERS = [color.rgb32(250, 240, 120), color.rgb32(240, 120, 160), color.rgb32(200, 160, 250)]


def add_plant(batch, rng, x=0.0, z=0.0, s=1.0):
    leaf = rng.choice([C['leaves_light'], C['leaves']])
    batch.add('icosphere', position=(x, 0.35 * s, z), scale=(1.1 * s, 0.8 * s, 1.1 * s), color=leaf)
    batch.add('icosphere', position=(x + 0.3 * s, 0.3 * s, z + 0.2 * s), scale=0.7 * s, color=leaf.tint(0.08))
    flower = rng.choice(HERB_FLOWERS)
    for _ in range(5):
        a = rng.uniform(0, math.tau)
        r = rng.uniform(0.2, 0.5) * s
        batch.add('gem', position=(x + math.cos(a) * r, 0.65 * s + rng.uniform(0, 0.1), z + math.sin(a) * r),
                  scale=0.16 * s, color=flower)


DEBRIS_COLORS = {'tree': C['trunk'], 'rock': C['rock'], 'plant': C['leaves_light']}


class Debris(Entity):
    """Lasquinha que voa ao golpear um recurso."""

    def __init__(self, position, c):
        super().__init__()
        self.visual = part(parent=self, scale=random.uniform(0.08, 0.16), color=c)
        self.position = position
        a = random.uniform(0, math.tau)
        self.velocity = Vec3(math.cos(a) * random.uniform(1, 3), random.uniform(3, 5.5), math.sin(a) * random.uniform(1, 3))
        self.life = 0.6

    def update(self):
        self.velocity.y -= 18 * time.dt
        self.position += self.velocity * time.dt
        self.visual.rotation_x += 400 * time.dt
        self.life -= time.dt
        if self.life <= 0 or self.y < 0:
            destroy(self.visual)
            destroy(self)


# ------------------------------------------------------------ recurso
class ResourceNode:
    """Um recurso que pode ser coletado com a ferramenta certa."""

    KINDS = {
        #         nome      ferramenta  golpes  recurso    por golpe  bonus final  renasce (s)
        'tree':  ('Árvore', AXE,        4,      'madeira', 1,         2,           120),
        'rock':  ('Rocha',  PICKAXE,    5,      'pedra',   1,         2,           150),
        'plant': ('Planta', SCYTHE,     1,      'ervas',   1,         1,           60),
    }

    def __init__(self, world, kind, x, z, data, radius):
        self.world = world
        self.kind = kind
        self.x, self.z = x, z
        self.verts, self.norms, self.cols = data   # malha ja em coordenadas do mundo
        (self.label, self.tool, self.max_hits, self.resource,
         self.per_hit, self.final_bonus, self.respawn_time) = self.KINDS[kind]
        self.radius = radius
        self.hits_left = self.max_hits
        self.depleted = False
        self.visible = True          # aparece na malha do chunk?
        self.regrow_timer = 0.0
        self.chunk = None
        self.obstacle = world.block(x, z, radius) if kind != 'plant' else None

    @property
    def position(self):
        return Vec3(self.x, 0, self.z)

    def hit(self, rng=random):
        """Golpe com a ferramenta certa. Retorna {item_id: quantidade} ganho."""
        if self.depleted:
            return {}
        self.hits_left -= 1
        gained = {self.resource: self.per_hit}
        if self.kind == 'plant' and rng.random() < 0.35:
            gained[rng.choice(['maca', 'uvas'])] = 1     # as vezes vem uma fruta junto
        for _ in range(4):
            Debris(Vec3(self.x, 0.8 if self.kind != 'plant' else 0.4, self.z), DEBRIS_COLORS[self.kind])
        if self.hits_left <= 0:
            gained[self.resource] += self.final_bonus
            self.deplete()
        return gained

    def _ghost(self):
        """Copia temporaria do modelo (para animar sem mexer no chunk)."""
        offset = Vec3(self.x, 0, self.z)
        mesh = Mesh(vertices=[v - offset for v in self.verts], normals=list(self.norms),
                    colors=list(self.cols), mode='triangle')
        return Entity(position=offset, model=mesh, shader=SHADER)

    def deplete(self):
        self.depleted = True
        self.visible = False
        self.regrow_timer = self.respawn_time
        if self.obstacle:
            self.obstacle.active = False
        self.chunk.rebuild()
        ghost = self._ghost()
        ghost.animate_scale(Vec3(1, 0.01, 1) if self.kind == 'tree' else 0.01, duration=0.35, curve=curve.in_back)
        destroy(ghost, delay=0.4)

    def regrow(self):
        self.depleted = False
        self.hits_left = self.max_hits
        if self.obstacle:
            self.obstacle.active = True
        ghost = self._ghost()
        ghost.scale = 0.01
        ghost.animate_scale(1, duration=1.2, curve=curve.out_back)
        invoke(self._finish_regrow, ghost, delay=1.25)

    def _finish_regrow(self, ghost):
        destroy(ghost)
        if not self.depleted:     # pode ter sido coletado de novo durante a animacao
            self.visible = True
            self.chunk.rebuild()

    def tick(self, dt, player_position):
        """Chamado pelo mundo enquanto o recurso esta esgotado."""
        self.regrow_timer -= dt
        if self.regrow_timer <= 0:
            # nao nasce em cima do jogador
            if math.hypot(self.x - player_position.x, self.z - player_position.z) > self.radius + 1.5:
                self.regrow()
            else:
                self.regrow_timer = 2


class Chunk:
    """Pedaco do mapa: junta os recursos visiveis numa unica malha."""

    def __init__(self):
        self.nodes = []
        self.entity = None

    def rebuild(self):
        verts, norms, cols = [], [], []
        for n in self.nodes:
            if n.visible:
                verts += n.verts
                norms += n.norms
                cols += n.cols
        if self.entity:
            destroy(self.entity)
            self.entity = None
        if verts:
            self.entity = Entity(model=Mesh(vertices=verts, normals=norms, colors=cols, mode='triangle'),
                                 shader=SHADER)
