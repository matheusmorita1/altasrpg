"""Construcao do mundo: vila (com as lojas), floresta, campina dos slimes,
acampamento goblin e cemiterio."""
import math
import random

from ursina import Vec3, color, time

from models import Glow, StaticBatch, part, flat
from resources import Chunk, ResourceNode, add_plant, add_rock, add_tree
from settings import C, WORLD_RADIUS, VILLAGE_RADIUS, WORLD_SEED

# Centros das regioes (x, z). Usados tambem pelo spawner em game.py.
SLIME_MEADOW = (-30, -24)
GOBLIN_CAMP = (48, 22)
GRAVEYARD = (-12, 60)

# Barracas das lojas na praca da vila (x, z). A frente de cada uma olha para o poco.
SHOP_SPOTS = {
    'food': (7.5, -2.0),
    'smith': (0.0, -8.0),
    'witch': (-7.5, 3.0),
}

GRID_CELL = 6
CHUNK_SIZE = 24      # tamanho dos pedacos do mapa que agrupam arvores/pedras/plantas


def _seg_distance(px, pz, ax, az, bx, bz):
    """Distancia do ponto P ao segmento AB (no plano XZ)."""
    abx, abz = bx - ax, bz - az
    t = ((px - ax) * abx + (pz - az) * abz) / (abx * abx + abz * abz)
    t = max(0.0, min(1.0, t))
    cx, cz = ax + abx * t, az + abz * t
    return math.hypot(px - cx, pz - cz)


def facing_center(x, z):
    """rotation_y para que o +z local aponte para o centro da vila."""
    return math.degrees(math.atan2(-x, -z))


class Obstacle:
    """Obstaculo circular. `active=False` desliga a colisao (ex.: arvore cortada)."""
    __slots__ = ('x', 'z', 'r', 'active')

    def __init__(self, x, z, r):
        self.x, self.z, self.r, self.active = x, z, r, True


class World:
    def __init__(self):
        self.rng = random.Random(WORLD_SEED)
        self.obstacles = []            # lista de Obstacle
        self._grid = {}                # (celula_x, celula_z) -> obstaculos
        self.static = StaticBatch()    # tudo que nao se mexe vira uma malha so
        self._node_batch = StaticBatch()
        self.nodes = []                # recursos coletaveis (ResourceNode)
        self.chunks = {}               # (cx, cz) -> Chunk com a malha dos recursos
        self.paths = [((0, 0), SLIME_MEADOW), ((0, 0), GOBLIN_CAMP), ((0, 0), GRAVEYARD)]
        self.fires = []
        self.glows = []                # halos das luzes (se dissolvem na nevoa)

        self._ground()
        self._paths()
        self._village()
        self._slime_meadow()
        self._goblin_camp()
        self._graveyard()
        self._forest()
        self._plants()
        self._border()

        # Junta milhares de pecas em poucas malhas (uma por pedaco do mapa) -> muito mais FPS
        self.static_chunks = self.static.build_chunks(CHUNK_SIZE)
        self._node_batch._tf.removeNode()   # libera o ajudante interno
        for chunk in self.chunks.values():
            chunk.rebuild()

    # ------------------------------------------------------------------ util
    def _add(self, model='cube', **kwargs):
        self.static.add(model, **kwargs)

    def block(self, x, z, r):
        """Registra um obstaculo circular numa grade espacial (colisao rapida)."""
        obstacle = Obstacle(x, z, r)
        self.obstacles.append(obstacle)
        reach = r + 1.5   # folga para o raio de quem colide
        x0, x1 = int((x - reach) // GRID_CELL), int((x + reach) // GRID_CELL)
        z0, z1 = int((z - reach) // GRID_CELL), int((z + reach) // GRID_CELL)
        for gx in range(x0, x1 + 1):
            for gz in range(z0, z1 + 1):
                self._grid.setdefault((gx, gz), []).append(obstacle)
        return obstacle

    _block = block

    def _nearby(self, x, z):
        return self._grid.get((int(x // GRID_CELL), int(z // GRID_CELL)), ())

    def is_free(self, x, z, margin=0.0):
        """True se o ponto nao estiver dentro de um obstaculo ativo."""
        for o in self.obstacles:
            if o.active and (x - o.x) ** 2 + (z - o.z) ** 2 < (o.r + margin) ** 2:
                return False
        return True

    def near_path(self, x, z, width=3.5):
        return any(_seg_distance(x, z, *a, *b) < width for a, b in self.paths)

    def resolve_collision(self, position, radius):
        """Empurra uma posicao para fora dos obstaculos e para dentro do mundo."""
        x, z = position.x, position.z
        for o in self._nearby(x, z):
            if not o.active:
                continue
            dx, dz = x - o.x, z - o.z
            min_d = o.r + radius
            d2 = dx * dx + dz * dz
            if d2 < min_d * min_d:
                d = math.sqrt(d2) or 0.0001
                x = o.x + dx / d * min_d
                z = o.z + dz / d * min_d
        d = math.hypot(x, z)
        if d > WORLD_RADIUS:
            x, z = x / d * WORLD_RADIUS, z / d * WORLD_RADIUS
        return Vec3(x, position.y, z)

    def _node(self, kind, x, z, builder, size, radius):
        batch = self._node_batch
        group = batch.group(position=(x, 0, z), rotation_y=self.rng.uniform(0, 360))
        batch.default_parent = group
        builder(batch, self.rng, 0, 0, size)
        batch.default_parent = None
        group.removeNode()
        node = ResourceNode(self, kind, x, z, batch.take_data(), radius)
        chunk = self.chunks.setdefault((int(x // CHUNK_SIZE), int(z // CHUNK_SIZE)), Chunk())
        chunk.nodes.append(node)
        node.chunk = chunk
        self.nodes.append(node)
        return node

    def nearest_node(self, position, max_distance):
        best, best_d = None, max_distance
        for node in self.nodes:
            if node.depleted:
                continue
            d = math.hypot(node.x - position.x, node.z - position.z) - node.radius
            if d < best_d:
                best, best_d = node, d
        return best

    # ---------------------------------------------------------------- chao
    def _ground(self):
        self.ground = part('plane', scale=(260, 1, 260), color=C['grass'])
        # manchas de grama para quebrar a monotonia
        for _ in range(140):
            a = self.rng.uniform(0, math.tau)
            d = self.rng.uniform(0, WORLD_RADIUS + 10)
            s = self.rng.uniform(3, 9)
            self._add('cylinder6', position=(math.cos(a) * d, 0.0, math.sin(a) * d),
                      scale=(s, 0.02, s * self.rng.uniform(0.6, 1.0)),
                      rotation_y=self.rng.uniform(0, 360),
                      color=self.rng.choice([C['grass_dark'], C['grass_light']]))
        # tufos de grama
        for _ in range(500):
            a = self.rng.uniform(0, math.tau)
            d = self.rng.uniform(0, WORLD_RADIUS)
            x, z = math.cos(a) * d, math.sin(a) * d
            if self.near_path(x, z, 2):
                continue
            self._add('pyramid', position=(x, 0, z), scale=(0.15, self.rng.uniform(0.25, 0.5), 0.15),
                      rotation_y=self.rng.uniform(0, 90), color=C['grass_dark'])

    def _paths(self):
        for (ax, az), (bx, bz) in self.paths:
            dx, dz = bx - ax, bz - az
            length = math.hypot(dx, dz)
            steps = int(length / 2.2)
            for i in range(steps):
                t = i / steps
                x = ax + dx * t + self.rng.uniform(-0.4, 0.4)
                z = az + dz * t + self.rng.uniform(-0.4, 0.4)
                s = self.rng.uniform(2.6, 3.4)
                self._add('cylinder6', position=(x, 0.01, z), scale=(s, 0.02, s),
                          rotation_y=self.rng.uniform(0, 60), color=C['path'])

    # ----------------------------------------------------------------- vila
    def _house(self, x, z, rot, roof_color):
        w, d, h = 5, 5, 3.4
        house = self.static.group(position=(x, 0, z), rotation_y=rot)
        self._add(parent=house, scale=(w, h, d), y=h / 2, color=C['wall'])
        # vigas de madeira nos cantos
        for sx in (-1, 1):
            for sz in (-1, 1):
                self._add(parent=house, scale=(0.3, h, 0.3), position=(sx * w / 2, h / 2, sz * d / 2), color=C['wood'])
        self._add(parent=house, scale=(w + 0.2, 0.25, d + 0.2), y=h, color=C['wood'])
        self._add('pyramid', parent=house, scale=(w * 1.55, 2.6, d * 1.55), y=h, rotation_y=45, color=roof_color)
        # porta e janelas (lado +z = frente)
        self._add(parent=house, scale=(1.1, 2.0, 0.1), position=(0, 1.0, d / 2 + 0.05), color=C['wood_dark'])
        for sx in (-1.6, 1.6):
            self._add(parent=house, scale=(0.8, 0.8, 0.1), position=(sx, 2.0, d / 2 + 0.05), color=C['window'])
        self._add(parent=house, scale=(0.1, 0.8, 0.8), position=(w / 2 + 0.05, 2.0, 0), color=C['window'])
        self._add(parent=house, scale=(0.1, 0.8, 0.8), position=(-w / 2 - 0.05, 2.0, 0), color=C['window'])
        # chamine
        self._add(parent=house, scale=(0.6, 2.0, 0.6), position=(1.4, h + 1.4, -1.0), color=C['stone'])
        self.block(x, z, 3.4)

    def _stall(self, kind, x, z):
        """Barraca de feira. A frente (+z local) fica virada para o centro da vila."""
        styles = {
            'food':  (color.rgb32(210, 60, 50), color.rgb32(245, 240, 230)),
            'smith': (color.rgb32(70, 70, 80), color.rgb32(150, 110, 70)),
            'witch': (color.rgb32(100, 50, 140), color.rgb32(40, 30, 50)),
        }
        stripe_a, stripe_b = styles[kind]
        g = self.static.group(position=(x, 0, z), rotation_y=facing_center(x, z))
        add = lambda model='cube', **kw: self._add(model, parent=g, **kw)  # noqa: E731

        add(scale=(3.2, 1.0, 0.9), position=(0, 0.5, 0.6), color=C['wood'])              # balcao
        add(scale=(3.4, 0.1, 1.1), position=(0, 1.05, 0.6), color=C['wood_dark'])         # tampo
        for sx in (-1.55, 1.55):
            add(scale=(0.16, 2.7, 0.16), position=(sx, 1.35, 1.05), color=C['wood_dark'])  # postes da frente
            add(scale=(0.16, 3.1, 0.16), position=(sx, 1.55, -1.3), color=C['wood_dark'])  # postes de tras
        for i in range(6):                                                                # toldo listrado
            add(scale=(0.58, 0.07, 2.9), position=(-1.45 + i * 0.58, 2.95, -0.1), rotation_x=-9,
                color=stripe_a if i % 2 == 0 else stripe_b)
        add(scale=(1.8, 0.6, 0.08), position=(0, 3.55, 1.0), color=C['wood'])            # placa

        if kind == 'food':
            add('gem', scale=0.42, position=(0, 3.55, 1.08), color=color.rgb32(220, 50, 50))   # maca na placa
            add('cube', scale=(0.06, 0.15, 0.06), position=(0, 3.82, 1.08), color=C['trunk'])
            fruit_colors = [color.rgb32(220, 50, 50), color.rgb32(250, 220, 70),
                            color.rgb32(140, 70, 180), color.rgb32(180, 210, 80)]
            for i, fc in enumerate(fruit_colors):                                        # cestos de frutas
                bx = -1.2 + i * 0.8
                add('cylinder', scale=(0.6, 0.25, 0.6), position=(bx, 1.1, 0.6), color=C['wood'].tint(0.1))
                for j in range(4):
                    add('gem', scale=0.2, position=(bx + (j % 2 - 0.5) * 0.2, 1.38 + j // 2 * 0.1,
                                                    0.6 + (j // 2 - 0.5) * 0.15), color=fc)
        elif kind == 'smith':
            add(scale=(0.5, 0.45, 0.08), position=(0, 3.55, 1.08), color=color.rgb32(60, 60, 66))  # bigorna na placa
            # bigorna e forja ao lado
            add(scale=(0.5, 0.5, 0.4), position=(2.4, 0.25, 0.8), color=color.rgb32(60, 60, 66))
            add(scale=(1.0, 0.3, 0.45), position=(2.4, 0.65, 0.8), color=color.rgb32(70, 70, 76))
            add('cylinder', scale=(1.2, 0.9, 1.2), position=(-2.6, 0, -0.3), color=C['stone'])
            # ferramentas expostas no balcao
            add(scale=(0.07, 0.9, 0.07), position=(-0.9, 1.2, 0.85), rotation_z=20, color=C['wood_dark'])
            add(scale=(0.5, 0.1, 0.1), position=(-1.05, 1.6, 0.85), rotation_z=20, color=color.rgb32(185, 190, 200))
            add(scale=(0.07, 0.9, 0.07), position=(0.9, 1.2, 0.85), rotation_z=-20, color=C['wood_dark'])
            add(scale=(0.3, 0.25, 0.06), position=(1.0, 1.55, 0.85), rotation_z=-20, color=color.rgb32(185, 190, 200))
            self.block(x + math.sin(math.radians(facing_center(x, z) + 90)) * 2.4,
                       z + math.cos(math.radians(facing_center(x, z) + 90)) * 2.4, 0.6)
        else:
            add('icosphere', scale=0.4, position=(0, 3.5, 1.08), color=color.rgb32(160, 80, 220))  # pocao na placa
            # caldeirao ao lado
            add('cylinder', scale=(1.1, 0.8, 1.1), position=(-2.5, 0, 0.6), color=color.rgb32(40, 40, 44))
            add('cylinder', scale=(1.0, 0.05, 1.0), position=(-2.5, 0.78, 0.6), color=color.rgb32(110, 230, 90))
            for i, pc in enumerate([color.rgb32(230, 40, 70), color.rgb32(255, 90, 160), color.rgb32(120, 90, 230),
                                    color.rgb32(230, 40, 70)]):
                bx = -1.1 + i * 0.7
                add('icosphere', scale=0.32, position=(bx, 1.27, 0.6), color=pc)
                add('cylinder', scale=(0.1, 0.15, 0.1), position=(bx, 1.4, 0.6), color=color.rgb32(200, 230, 240))
            self.block(x + math.sin(math.radians(facing_center(x, z) - 90)) * 2.5,
                       z + math.cos(math.radians(facing_center(x, z) - 90)) * 2.5, 0.7)
        self.block(x, z, 1.7)

    def _village(self):
        houses = [(-10, 7.5, 150, C['roof']), (5, 10, 200, C['roof_blue']), (-11, -1, 95, C['roof_blue']),
                  (10, -8, -50, C['roof'])]
        for x, z, rot, roof in houses:
            self._house(x, z, rot, roof)

        for kind, (x, z) in SHOP_SPOTS.items():
            self._stall(kind, x, z)

        # praca central de pedra com um poco
        self._add('cylinder', position=(0, 0.015, 0), scale=(9, 0.03, 9), color=C['path'])
        self._add('cylinder', position=(0, 0, 0), scale=(2.2, 0.9, 2.2), color=C['stone'])
        self._add('cylinder', position=(0, 0.5, 0), scale=(1.7, 0.45, 1.7), color=color.rgb32(50, 90, 140))
        for sx in (-1, 1):
            self._add(scale=(0.18, 2.4, 0.18), position=(sx * 0.95, 1.2, 0), color=C['wood'])
        self._add('pyramid', position=(0, 2.4, 0), scale=(2.8, 1.0, 2.8), rotation_y=45, color=C['roof'])
        self.block(0, 0, 1.3)

        # barris e caixas
        for x, z in [(-5.5, 10.5), (5.2, 13.5), (-12.5, -5.5), (13.5, -3.5), (4.5, -12.5)]:
            self._add('cylinder', position=(x, 0, z), scale=(0.9, 1.1, 0.9), color=C['wood'])
            self._add('cylinder', position=(x, 0.3, z), scale=(0.95, 0.08, 0.95), color=C['wood_dark'])
            self._add(position=(x + 1.0, 0.4, z + 0.3), scale=0.8, rotation_y=20, color=C['wood_dark'])
            self.block(x + 0.4, z, 1.1)

        # cerca baixa em volta da vila (com aberturas nas estradas)
        r = VILLAGE_RADIUS + 1
        for i in range(72):
            a = i / 72 * math.tau
            x, z = math.cos(a) * r, math.sin(a) * r
            if self.near_path(x, z, 4.5):
                continue
            self._add(position=(x, 0.55, z), scale=(0.2, 1.1, 0.2), color=C['wood'])
            a2 = (i + 0.5) / 72 * math.tau
            self._add(position=(math.cos(a2) * r, 0.75, math.sin(a2) * r), scale=(0.1, 0.12, 1.5),
                      rotation_y=-math.degrees(a2), color=C['wood'])

        # lanternas
        for x, z in [(-3.5, 3.5), (3.5, -3.5), (3.5, 3.5), (-3.5, -3.5)]:
            self._add(position=(x, 1.3, z), scale=(0.15, 2.6, 0.15), color=C['wood_dark'])
            flat(position=(x, 2.7, z), scale=0.35, color=color.rgb32(255, 220, 140))
            self.glows.append(Glow((x, 2.7, z), color.rgb32(255, 210, 130), size=1.3, strength=0.3))

    # -------------------------------------------------------- campina slime
    def _slime_meadow(self):
        cx, cz = SLIME_MEADOW
        # flores
        for _ in range(160):
            a = self.rng.uniform(0, math.tau)
            d = self.rng.uniform(0, 24)
            x, z = cx + math.cos(a) * d, cz + math.sin(a) * d
            c = self.rng.choice([color.rgb32(250, 240, 120), color.rgb32(240, 120, 160),
                                 color.rgb32(255, 255, 255), color.rgb32(170, 140, 240)])
            self._add(position=(x, 0.2, z), scale=(0.04, 0.4, 0.04), color=C['grass_dark'])
            self._add('gem', position=(x, 0.42, z), scale=0.18, color=c)
        # rochas (podem ser quebradas com a picareta)
        for _ in range(7):
            a = self.rng.uniform(0, math.tau)
            d = self.rng.uniform(6, 20)
            self._rock(cx + math.cos(a) * d, cz + math.sin(a) * d, self.rng.uniform(1, 1.8))

    # ---------------------------------------------------- acampamento goblin
    def _goblin_camp(self):
        cx, cz = GOBLIN_CAMP
        # chao de terra batida
        self._add('cylinder6', position=(cx, 0.02, cz), scale=(26, 0.02, 26), color=C['dirt'])
        # fogueira central
        for i in range(5):
            a = i / 5 * 360
            self._add(position=(cx, 0.15, cz), scale=(0.25, 0.25, 1.6), rotation_y=a, color=C['wood_dark'])
        for i in range(8):
            a = i / 8 * math.tau
            self._add('icosphere', position=(cx + math.cos(a) * 1.1, 0.15, cz + math.sin(a) * 1.1),
                      scale=0.45, color=C['rock_dark'])
        fire = flat('cone', position=(cx, 0.2, cz), scale=(1.0, 1.6, 1.0), color=C['fire'])
        flat('cone', parent=fire, scale=(0.6, 0.75, 0.6), color=color.rgb32(255, 230, 90))
        self.fires.append(fire)
        self.glows.append(Glow((cx, 1.1, cz), color.rgb32(255, 140, 50), size=4.0, strength=0.6, flicker=True))
        self.block(cx, cz, 1.2)

        # tendas
        for i in range(5):
            a = i / 5 * math.tau + 0.4
            x, z = cx + math.cos(a) * 8, cz + math.sin(a) * 8
            self._add('pyramid', position=(x, 0, z), scale=(4.2, 3.2, 4.2), rotation_y=self.rng.uniform(0, 90),
                      color=self.rng.choice([C['tent'], C['tent2']]))
            self._add(position=(x, 1.7, z), scale=(0.15, 3.4, 0.15), color=C['wood_dark'])
            self.block(x, z, 2.2)

        # palicada (estacas) com abertura virada para a vila
        to_village = math.atan2(-cz, -cx)
        for i in range(64):
            a = i / 64 * math.tau
            diff = abs((a - to_village + math.pi) % math.tau - math.pi)
            if diff < 0.32:
                continue
            x, z = cx + math.cos(a) * 14, cz + math.sin(a) * 14
            h = self.rng.uniform(2.2, 2.8)
            self._add('cylinder6', position=(x, 0, z), scale=(0.55, h, 0.55), color=C['wood'])
            self._add('cone', position=(x, h, z), scale=(0.55, 0.6, 0.55), color=C['wood'])
            self.block(x, z, 0.45)

        # caveira no totem
        self._add('cylinder6', position=(cx + 3, 0, cz - 3), scale=(0.4, 3, 0.4), color=C['wood_dark'])
        self._add(position=(cx + 3, 3.2, cz - 3), scale=0.55, color=color.rgb32(235, 230, 210))
        self.block(cx + 3, cz - 3, 0.4)

    # ------------------------------------------------------------- cemiterio
    def _graveyard(self):
        cx, cz = GRAVEYARD
        self._add('cylinder6', position=(cx, 0.02, cz), scale=(34, 0.02, 30), color=C['grave_ground'])
        # lapides e cruzes em fileiras
        for row in range(-3, 4):
            for col in range(-4, 5):
                if self.rng.random() < 0.35:
                    continue
                x = cx + col * 3.2 + self.rng.uniform(-0.4, 0.4)
                z = cz + row * 3.4 + self.rng.uniform(-0.4, 0.4)
                if abs(col) <= 0 and row < 1:
                    continue   # corredor de entrada
                tilt = self.rng.uniform(-8, 8)
                if self.rng.random() < 0.6:
                    self._add(position=(x, 0.6, z), scale=(0.9, 1.2, 0.25), rotation=(0, 0, tilt),
                              color=C['tombstone'])
                    self._add('cylinder', position=(x, 1.2, z), scale=(0.9, 0.25, 0.9),
                              rotation=(90, 0, tilt), color=C['tombstone'])
                else:
                    self._add(position=(x, 0.8, z), scale=(0.18, 1.6, 0.18), rotation=(0, 0, tilt),
                              color=C['dead_wood'])
                    self._add(position=(x, 1.15, z), scale=(0.8, 0.16, 0.16), rotation=(0, 0, tilt),
                              color=C['dead_wood'])
                self._add(position=(x, 0.03, z + 0.9), scale=(0.9, 0.06, 1.6), color=C['dirt'])
                self.block(x, z, 0.55)
        # cerca de ferro
        for i in range(70):
            a = i / 70 * math.tau
            x, z = cx + math.cos(a) * 17, cz + math.sin(a) * 15
            if self.near_path(x, z, 3):
                continue
            self._add(position=(x, 0.7, z), scale=(0.1, 1.4, 0.1), color=color.rgb32(40, 40, 46))
        # arvores mortas
        for _ in range(8):
            a = self.rng.uniform(0, math.tau)
            d = self.rng.uniform(10, 15)
            self._dead_tree(cx + math.cos(a) * d, cz + math.sin(a) * d * 0.85)

    # ---------------------------------------------------------------- natureza
    def _tree(self, x, z, scale=1.0):
        """Arvore que pode ser cortada com machado."""
        self._node('tree', x, z, add_tree, scale, 0.45 * scale)

    def _rock(self, x, z, s):
        """Rocha que pode ser quebrada com picareta."""
        self._node('rock', x, z, add_rock, s, s * 0.6)

    def _dead_tree(self, x, z):
        h = self.rng.uniform(2.5, 4)
        self._add('cylinder6', position=(x, 0, z), scale=(0.4, h, 0.4), color=C['dead_wood'])
        for _ in range(3):
            self._add(position=(x, h * self.rng.uniform(0.55, 0.9), z), scale=(0.12, 1.6, 0.12),
                      rotation=(self.rng.uniform(-50, 50), self.rng.uniform(0, 360), self.rng.uniform(30, 60)),
                      color=C['dead_wood'])
        self.block(x, z, 0.4)

    def _forest(self):
        clearings = [((0, 0), VILLAGE_RADIUS + 5), (SLIME_MEADOW, 17), (GOBLIN_CAMP, 17), (GRAVEYARD, 20)]
        placed = 0
        tries = 0
        while placed < 230 and tries < 5000:
            tries += 1
            a = self.rng.uniform(0, math.tau)
            d = math.sqrt(self.rng.uniform(0, 1)) * (WORLD_RADIUS - 2)
            x, z = math.cos(a) * d, math.sin(a) * d
            if any(math.hypot(x - c[0], z - c[1]) < r for c, r in clearings):
                continue
            if self.near_path(x, z, 4) or not self.is_free(x, z, 1.8):
                continue
            if self.rng.random() < 0.15:
                self._rock(x, z, self.rng.uniform(0.8, 2.0))
            else:
                self._tree(x, z, self.rng.uniform(0.8, 1.35))
            placed += 1
        # algumas rochas logo fora da vila, para testar a picareta cedo
        for i in range(5):
            a = math.radians(-60 + i * 22)
            d = self.rng.uniform(20, 25)
            x, z = math.cos(a) * d, math.sin(a) * d
            if self.is_free(x, z, 1.5) and not self.near_path(x, z, 3):
                self._rock(x, z, self.rng.uniform(0.9, 1.3))

    def _plants(self):
        """Plantas de ervas espalhadas pelo mapa (colhidas com a foice)."""
        blocked = [((0, 0), VILLAGE_RADIUS + 2), (GOBLIN_CAMP, 15), (GRAVEYARD, 18)]
        placed, tries = 0, 0
        while placed < 70 and tries < 3000:
            tries += 1
            if placed < 20:   # boa parte perto da vila e da campina
                a = self.rng.uniform(0, math.tau)
                d = self.rng.uniform(18, 32)
                x, z = math.cos(a) * d, math.sin(a) * d
            else:
                a = self.rng.uniform(0, math.tau)
                d = math.sqrt(self.rng.uniform(0, 1)) * (WORLD_RADIUS - 4)
                x, z = math.cos(a) * d, math.sin(a) * d
            if any(math.hypot(x - c[0], z - c[1]) < r for c, r in blocked):
                continue
            if self.near_path(x, z, 2.5) or not self.is_free(x, z, 1.2):
                continue
            self._node('plant', x, z, add_plant, self.rng.uniform(0.8, 1.1), 0.6)
            placed += 1

    def _border(self):
        """Anel denso de arvores marcando o limite do mundo (decorativas)."""
        for ring, r in enumerate((WORLD_RADIUS + 4, WORLD_RADIUS + 8, WORLD_RADIUS + 13)):
            n = int(math.tau * r / (4.2 + ring))
            for i in range(n):
                a = (i + ring * 0.5) / n * math.tau
                rr = r + self.rng.uniform(-1, 1)
                add_tree(self.static, self.rng, math.cos(a) * rr, math.sin(a) * rr, self.rng.uniform(1.2, 1.7))

    # ------------------------------------------------------------- animacao
    def update(self, player_position):
        for fire in self.fires:
            fire.scale_y = 1.6 + math.sin(time.time() * 13) * 0.15 + math.sin(time.time() * 7.3) * 0.1
            fire.rotation_y += 90 * time.dt
        dt = time.dt
        for node in self.nodes:
            if node.depleted:
                node.tick(dt, player_position)
