"""Formas low-poly geradas no codigo + um 'batch' que junta o cenario numa malha so.

Formas disponiveis (todas com sombreamento facetado):
  'cube'      cubo centrado na origem, lado 1
  'cylinder'  prisma de 8 lados, base em y=0 e topo em y=1, raio 0.5
  'cylinder6' prisma de 6 lados
  'cone'      cone de 7 lados, base em y=0 e ponta em y=1
  'pyramid'   piramide de 4 lados (cantos nos eixos; use rotation_y=45 para alinhar)
  'icosphere' esfera facetada (raio 0.5)
  'gem'       icosaedro simples (raio 0.5), mais barato
Qualquer outro nome e repassado ao Ursina ('quad', 'circle', 'plane'...).
"""
import math

import time

from panda3d.core import ColorBlendAttrib, LPoint3f, LVector3f, Mat3
from ursina import Entity, Mesh, Shader, camera, color, destroy, invoke, scene
from ursina.shaders import lit_with_shadows_shader as _base_shader
from ursina.shaders.unlit_shader import unlit_shader
from ursina.shaders.unlit_with_fog_shader import unlit_with_fog_shader as _unlit_fog_shader

from settings import FOG_COLOR, FOG_END, FOG_START, SHADOW_BLUR, SHADOW_SAMPLES, VIEW_DISTANCE

# ------------------------------------------------------------------ shader
# Copia do shader iluminado do Ursina com duas mudancas:
#  1. nevoa corrigida: o original ignora fog_start (a nevoa comecava colada na camera).
#     Aqui ela comeca em fog_start e cresce suavemente ate fog_end.
#  2. inputs "globais" (camera, nevoa, qualidade da sombra) sao enviados UMA vez para a
#     raiz da cena, em vez de uma vez por entidade a cada frame (o Panda3D herda inputs
#     de shader pela arvore da cena).
_OLD_FOG = '''    float t = distance_to_camera/fog_length;
    t = clamp(t, 0., 1.);'''
_NEW_FOG = '''    float t = clamp((distance_to_camera - fog_start) / max(fog_length, 0.001), 0., 1.);
    t = t * t * (3.0 - 2.0 * t);'''
assert _OLD_FOG in _base_shader.fragment, 'shader do Ursina mudou: revise a nevoa em models.py'

_GLOBAL_INPUTS = ('camera_world_position', 'fog_color', 'fog_start', 'fog_end', 'shadow_samples', 'shadow_blur')

SHADER = Shader(name='lit_fog_shader', language=Shader.GLSL, vertex=_base_shader.vertex,
                fragment=_base_shader.fragment.replace(_OLD_FOG, _NEW_FOG),
                default_input={k: v for k, v in _base_shader.default_input.items() if k not in _GLOBAL_INPUTS})

# O shader PADRAO do Ursina (unlit_with_fog) tambem e usado por toda entidade "agrupadora"
# (pivos de bracos, corpo dos mobs, NPCs...) e por efeitos sem luz (fogo, luminarias).
# Ele grava em cada entidade uma nevoa transparente (fog_color = clear), e no Panda3D os
# filhos herdam do ancestral mais proximo: por isso mobs e NPCs ignoravam a nevoa.
# Corrigimos o shader padrao: sem inputs de nevoa proprios (herda da cena) e com a mesma
# formula de nevoa suave do shader iluminado.
assert _OLD_FOG in _unlit_fog_shader.fragment, 'shader do Ursina mudou: revise a nevoa em models.py'
_unlit_fog_shader.fragment = _unlit_fog_shader.fragment.replace(_OLD_FOG, _NEW_FOG)
for _key in _GLOBAL_INPUTS:
    _unlit_fog_shader.default_input.pop(_key, None)
_unlit_fog_shader.continuous_input.pop('camera_world_position', None)
_unlit_fog_shader.compiled = False
_unlit_fog_shader.compile()     # entidades criadas daqui em diante usam a versao corrigida


def setup_shared_shader_inputs():
    """Valores fixos (nevoa e qualidade da sombra), enviados uma vez para toda a cena."""
    scene.set_shader_input('fog_color', FOG_COLOR)
    scene.set_shader_input('fog_start', FOG_START)
    scene.set_shader_input('fog_end', FOG_END)
    scene.set_shader_input('shadow_samples', SHADOW_SAMPLES)
    scene.set_shader_input('shadow_blur', SHADOW_BLUR)


def update_shared_shader_inputs():
    """Chamado a cada frame: a posicao da camera (usada pela nevoa e pela luz)."""
    scene.set_shader_input('camera_world_position', camera.world_position)


# ----------------------------------------------------------------- brilho
class Glow(Entity):
    """Halo de luz (fogueira, luminaria) que se dissolve na nevoa em vez de sumir de repente.

    Perto: um brilho pequeno e forte. Conforme a distancia aumenta, o halo cresce e
    enfraquece, como uma luz espalhada pela neblina, e chega a zero um pouco antes
    do limite de visao (por isso nunca "pisca" ao entrar/sair do alcance).
    """

    night = 0.0     # 0 = dia, 1 = noite (definido pelo jogo): a noite deixa os brilhos mais fortes

    def __init__(self, position, glow_color, size=1.5, strength=0.55, flicker=False, **kwargs):
        super().__init__(model='quad', texture='radial_gradient', position=position, billboard=True,
                         color=glow_color, scale=size, shader=unlit_shader, **kwargs)
        self.base_color = glow_color
        self.base_size = size
        self.strength = strength
        self.flicker = flicker
        self.setDepthWrite(False)
        self.setBin('fixed', 5)
        self.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                             ColorBlendAttrib.O_one))   # brilho aditivo (soma luz)
        self.update()

    def update(self):
        d = (self.world_position - camera.world_position).length()
        far = VIEW_DISTANCE - 3
        k = min(1.0, max(0.0, (d - FOG_START) / (far - FOG_START)))
        k = k * k * (3 - 2 * k)
        alpha = min(1.0, self.strength * (1 + 1.4 * Glow.night)) * (1 - k)
        if self.flicker:
            alpha *= 0.85 + 0.15 * math.sin(time.time() * 11) * math.sin(time.time() * 7.3)
        self.scale = self.base_size * (1 + 1.5 * k)          # luz "espalhada" na nevoa
        self.color = color.rgba(self.base_color[0], self.base_color[1], self.base_color[2], alpha)


# ------------------------------------------------------------ dormencia
def set_dormant(entity, dormant):
    """Congela (ou acorda) uma entidade e todos os filhos.

    Uma entidade dormente nao e desenhada e o loop do Ursina pula ela e seus filhos
    logo na primeira verificacao (`ignore`), sem custo de Python por frame.
    """
    if getattr(entity, 'dormant', False) == dormant:
        return
    entity.dormant = dormant
    entity.enabled = not dormant
    for child in entity.get_descendants():
        child.ignore = dormant

_cache = {}


# ----------------------------------------------------------- geometria
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(v):
    length = math.sqrt(_dot(v, v)) or 1
    return (v[0] / length, v[1] / length, v[2] / length)


def _faceted(triangles, center):
    """Recebe triangulos (convexos em volta de `center`) e devolve
    vertices + normais facetadas, com a ordem de vertices que o Ursina espera."""
    verts, norms = [], []
    for a, b, c in triangles:
        cross = _cross(_sub(b, a), _sub(c, a))
        centroid = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3, (a[2] + b[2] + c[2]) / 3)
        outward = _sub(centroid, center)
        if _dot(cross, outward) > 0:     # no Ursina a face da frente tem o produto vetorial "para dentro"
            b, c = c, b
        n = _norm(outward if _dot(cross, cross) == 0 else _cross(_sub(c, a), _sub(b, a)))
        for v in (a, b, c):
            verts.append(LPoint3f(*v))
            norms.append(LVector3f(*n))
    return verts, norms


def _cube():
    h = 0.5
    p = [(x, y, z) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    tris = []
    for a, b, c, d in faces:
        tris += [(p[a], p[b], p[c]), (p[a], p[c], p[d])]
    return _faceted(tris, (0, 0, 0))


def _ring(n, y, r=0.5):
    return [(math.cos(i / n * math.tau) * r, y, math.sin(i / n * math.tau) * r) for i in range(n)]


def _prism(n):
    bottom, top = _ring(n, 0), _ring(n, 1)
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris += [(bottom[i], bottom[j], top[j]), (bottom[i], top[j], top[i])]
        tris.append(((0, 1, 0), top[i], top[j]))
    return _faceted(tris, (0, 0.5, 0))


def _cone(n):
    base = _ring(n, 0)
    tris = [(base[i], base[(i + 1) % n], (0, 1, 0)) for i in range(n)]
    tris += [(base[i], base[(i + 1) % n], (0, 0, 0)) for i in range(n)]
    return _faceted(tris, (0, 0.3, 0))


def _icosphere(subdivisions):
    t = (1 + math.sqrt(5)) / 2
    p = [_norm(v) for v in [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
                            (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
             (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    tris = [(p[a], p[b], p[c]) for a, b, c in faces]
    for _ in range(subdivisions):
        new = []
        for a, b, c in tris:
            ab = _norm(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2))
            bc = _norm(((b[0] + c[0]) / 2, (b[1] + c[1]) / 2, (b[2] + c[2]) / 2))
            ca = _norm(((c[0] + a[0]) / 2, (c[1] + a[1]) / 2, (c[2] + a[2]) / 2))
            new += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        tris = new
    tris = [tuple((v[0] * 0.5, v[1] * 0.5, v[2] * 0.5) for v in tri) for tri in tris]
    return _faceted(tris, (0, 0, 0))


_BUILDERS = {
    'cube': _cube,
    'cylinder': lambda: _prism(8),
    'cylinder6': lambda: _prism(6),
    'cone': lambda: _cone(7),
    'pyramid': lambda: _cone(4),
    'icosphere': lambda: _icosphere(1),
    'gem': lambda: _icosphere(0),
}


def shape_data(name):
    if name not in _cache:
        _cache[name] = _BUILDERS[name]()
    return _cache[name]


def make_mesh(name):
    verts, norms = shape_data(name)
    return Mesh(vertices=list(verts), normals=list(norms), mode='triangle')


# ------------------------------------------------------------ entidades
def destroy_tree(entity, delay=0):
    """destroy() do Ursina nao remove os filhos da lista de atualizacao;
    esta versao destroi a entidade e todos os descendentes."""
    if delay:
        invoke(destroy_tree, entity, delay=delay)
        return
    if not entity:
        return
    for child in entity.get_descendants():
        destroy(child)
    destroy(entity)


def part(model='cube', **kwargs):
    """Cria uma peca iluminada (recebe luz e projeta sombra)."""
    kwargs.setdefault('shader', SHADER)
    return Entity(model=make_mesh(model) if model in _BUILDERS else model, **kwargs)


def flat(model='cube', **kwargs):
    """Peca sem iluminacao (efeitos, fogo, brilhos)."""
    kwargs.setdefault('unlit', True)
    return Entity(model=make_mesh(model) if model in _BUILDERS else model, **kwargs)


class StaticBatch:
    """Acumula pecas estaticas e gera UMA malha no final.

    Muito mais rapido que criar milhares de Entities: o cenario inteiro vira uma unica
    chamada de desenho.
    """

    def __init__(self):
        self.verts, self.norms, self.cols = [], [], []
        self._tf = Entity(add_to_scene_entities=False)
        self._groups = []
        self.default_parent = None     # grupo usado quando add() nao recebe parent

    def group(self, **transform):
        """Cria um 'grupo' (ex.: uma casa) para posicionar pecas relativas a ele."""
        g = Entity(add_to_scene_entities=False, **transform)
        self._groups.append(g)
        return g

    def add(self, model='cube', parent=None, color=None, **transform):
        tf = self._tf
        if parent is None:
            parent = self.default_parent if self.default_parent is not None else scene
        tf.parent = parent
        tf.position = (0, 0, 0)
        tf.rotation = (0, 0, 0)
        tf.scale = (1, 1, 1)
        for key, value in transform.items():
            setattr(tf, key, value)
        mat = tf.getMat(scene)
        normal_mat = Mat3(mat.getUpper3())
        normal_mat.invertInPlace()
        normal_mat.transposeInPlace()

        verts, norms = shape_data(model)
        self.verts.extend(mat.xformPoint(v) for v in verts)
        for n in norms:
            n = normal_mat.xform(n)
            n.normalize()
            self.norms.append(n)
        self.cols.extend([color] * len(verts))

    def take_data(self):
        """Devolve (vertices, normais, cores) acumulados e esvazia o batch (pode ser reusado)."""
        data = (self.verts, self.norms, self.cols)
        self.verts, self.norms, self.cols = [], [], []
        return data

    def take_mesh(self):
        verts, norms, cols = self.take_data()
        return Mesh(vertices=verts, normals=norms, colors=cols, mode='triangle')

    def _cleanup(self):
        for g in self._groups:
            g.removeNode()
        self._tf.removeNode()

    def build(self):
        mesh = self.take_mesh()
        self._cleanup()
        return Entity(model=mesh, shader=SHADER)

    def build_chunks(self, size):
        """Como build(), mas divide o cenario em pedacos de `size` x `size` metros.

        Cada pedaco e uma malha separada: o que fica alem da distancia de visao (ou fora
        da area de sombra) e descartado inteiro pela GPU, em vez de desenhar o mapa todo.
        """
        verts, norms, cols = self.take_data()
        cells = {}
        for i in range(0, len(verts), 3):
            a, b, c = verts[i], verts[i + 1], verts[i + 2]
            key = (int((a[0] + b[0] + c[0]) / 3 // size), int((a[2] + b[2] + c[2]) / 3 // size))
            bucket = cells.get(key)
            if bucket is None:
                bucket = cells[key] = ([], [], [])
            bucket[0].extend(verts[i:i + 3])
            bucket[1].extend(norms[i:i + 3])
            bucket[2].extend(cols[i:i + 3])
        self._cleanup()
        return [Entity(model=Mesh(vertices=v, normals=n, colors=c, mode='triangle'), shader=SHADER)
                for v, n, c in cells.values()]
