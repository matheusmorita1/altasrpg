"""Modelos 3D das armas e ferramentas que o heroi segura.

Todos sao montados com o cabo na origem (a mao) e a ponta apontando para +y.
"""
from ursina import Entity, color

from models import part

WOOD = color.rgb32(196, 150, 96)
WOOD_DARK = color.rgb32(120, 82, 46)
HANDLE = color.rgb32(92, 60, 34)
STONE = color.rgb32(150, 150, 156)
STONE_DARK = color.rgb32(112, 112, 120)
METAL = color.rgb32(185, 190, 200)


def _sword(root, blade, guard, length=1.0, width=0.13):
    part(parent=root, scale=(0.07, 0.28, 0.07), color=HANDLE)                               # cabo
    part(parent=root, scale=(0.1, 0.1, 0.1), y=-0.16, color=guard)                           # pomo
    part(parent=root, scale=(0.36, 0.07, 0.11), y=0.16, color=guard)                         # guarda
    part(parent=root, scale=(width, length, 0.05), y=0.2 + length / 2, color=blade)          # lamina
    part('pyramid', parent=root, scale=(width, 0.16, 0.05), y=0.2 + length, color=blade)     # ponta
    part(parent=root, scale=(0.02, length * 0.85, 0.052), y=0.2 + length / 2, color=blade.tint(-0.15))


def _wood_sword(root):
    _sword(root, WOOD, WOOD_DARK)


def _stone_sword(root):
    _sword(root, STONE, STONE_DARK, length=1.05, width=0.17)
    # lascas na lamina para parecer pedra talhada
    for y, x in ((0.5, 0.07), (0.85, -0.07), (1.05, 0.06)):
        part(parent=root, scale=(0.05, 0.12, 0.06), position=(x, y, 0), rotation_z=30, color=STONE_DARK)


def _stone_hammer(root):
    part(parent=root, scale=(0.08, 1.05, 0.08), y=0.35, color=HANDLE)
    part(parent=root, scale=(0.5, 0.3, 0.3), y=0.95, color=STONE)
    part(parent=root, scale=(0.52, 0.08, 0.32), y=0.95, color=STONE_DARK)
    part(parent=root, scale=(0.1, 0.34, 0.34), position=(0.27, 0.95, 0), color=STONE_DARK)
    part(parent=root, scale=(0.1, 0.34, 0.34), position=(-0.27, 0.95, 0), color=STONE_DARK)


def _pickaxe(root):
    part(parent=root, scale=(0.07, 0.95, 0.07), y=0.3, color=HANDLE)
    part(parent=root, scale=(0.75, 0.1, 0.1), y=0.78, color=METAL)
    part('pyramid', parent=root, scale=(0.1, 0.22, 0.1), position=(0.43, 0.78, 0), rotation_z=-90, color=METAL)
    part('pyramid', parent=root, scale=(0.1, 0.22, 0.1), position=(-0.43, 0.78, 0), rotation_z=90, color=METAL)


def _axe(root):
    part(parent=root, scale=(0.07, 0.95, 0.07), y=0.3, color=HANDLE)
    part(parent=root, scale=(0.32, 0.3, 0.06), position=(0.18, 0.68, 0), color=METAL)
    part(parent=root, scale=(0.06, 0.4, 0.07), position=(0.35, 0.68, 0), color=METAL.tint(0.15))
    part(parent=root, scale=(0.1, 0.12, 0.09), position=(-0.06, 0.7, 0), color=METAL.tint(-0.2))


def _scythe(root):
    part(parent=root, scale=(0.06, 1.15, 0.06), y=0.4, color=HANDLE)
    part(parent=root, scale=(0.12, 0.08, 0.08), position=(0.06, 0.15, 0), color=HANDLE)   # pegador
    # lamina curva: tres segmentos
    part(parent=root, scale=(0.32, 0.07, 0.03), position=(0.16, 0.95, 0), rotation_z=-8, color=METAL)
    part(parent=root, scale=(0.26, 0.06, 0.03), position=(0.42, 0.88, 0), rotation_z=-28, color=METAL)
    part(parent=root, scale=(0.16, 0.05, 0.03), position=(0.58, 0.77, 0), rotation_z=-50, color=METAL)


BUILDERS = {
    'wood_sword': _wood_sword,
    'stone_sword': _stone_sword,
    'stone_hammer': _stone_hammer,
    'pickaxe': _pickaxe,
    'axe': _axe,
    'scythe': _scythe,
}


def build_held(parent, item_def):
    """Monta o modelo do item na mao. Retorna a entidade raiz."""
    root = Entity(parent=parent)
    BUILDERS.get(item_def.model, _wood_sword)(root)
    return root
