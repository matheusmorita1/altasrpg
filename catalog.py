"""Catalogo de todos os itens do jogo e receitas de fabricacao.

Para criar um item novo basta adiciona-lo em ITEMS (e, se for fabricavel, em RECIPES).
"""
from dataclasses import dataclass, field

from ursina import color

# tipos de item
FOOD = 'food'
POTION = 'potion'
TOOL = 'tool'
WEAPON = 'weapon'
MATERIAL = 'material'

# ferramentas -> o que coletam
PICKAXE = 'pickaxe'   # quebra pedras
AXE = 'axe'           # corta arvores
SCYTHE = 'scythe'     # colhe plantas

# qual item e cada ferramenta
TOOL_ITEM = {PICKAXE: 'picareta', AXE: 'machado', SCYTHE: 'foice'}


@dataclass(frozen=True)
class ItemDef:
    id: str
    name: str
    kind: str
    description: str = ''
    price: int = 0              # preco na loja (0 = nao vendido)
    max_stack: int = 99
    icon_color: color.Color = color.white
    # comida / pocao
    heal: int = 0               # vida fixa curada
    heal_ratio: float = 0.0     # fracao da vida maxima curada
    hunger: int = 0             # quanto enche a barra de fome
    # arma / ferramenta (tudo que se segura na mao)
    damage: int = 0
    reach: float = 2.4
    swing_time: float = 0.5
    tool: str = ''              # PICKAXE / AXE / SCYTHE
    model: str = ''             # modelo 3D usado na mao (ver weapons.py)

    @property
    def equippable(self):
        return self.kind in (WEAPON, TOOL)

    @property
    def consumable(self):
        return self.kind in (FOOD, POTION)


def _items(*defs):
    return {d.id: d for d in defs}


ITEMS = _items(
    # ------------------------------------------------------------ alimentos
    ItemDef('maca', 'Maçã', FOOD, 'Crocante e equilibrada.', price=5,
            heal=10, hunger=15, icon_color=color.rgb32(220, 50, 50)),
    ItemDef('banana', 'Banana', FOOD, 'Mata bem a fome, cura pouco.', price=6,
            heal=6, hunger=25, icon_color=color.rgb32(250, 220, 70)),
    ItemDef('uvas', 'Uvas', FOOD, 'Cura bastante, enche pouco.', price=8,
            heal=18, hunger=10, icon_color=color.rgb32(140, 70, 180)),
    ItemDef('pera', 'Pêra', FOOD, 'A refeição mais completa.', price=10,
            heal=14, hunger=30, icon_color=color.rgb32(180, 210, 80)),

    # -------------------------------------------------------------- pocoes
    ItemDef('pocao_vida', 'Poção de Vida', POTION, 'Restaura 40% da vida.', price=25,
            heal_ratio=0.4, max_stack=10, icon_color=color.rgb32(230, 40, 70)),
    ItemDef('pocao_grande', 'Poção de Vida Grande', POTION, 'Restaura toda a vida.', price=60,
            heal_ratio=1.0, max_stack=5, icon_color=color.rgb32(255, 90, 160)),

    # --------------------------------------------------------- ferramentas
    ItemDef('picareta', 'Picareta', TOOL, 'Quebra pedras e rochas.', price=40, max_stack=1,
            damage=3, swing_time=0.55, tool=PICKAXE, model='pickaxe', icon_color=color.rgb32(150, 150, 160)),
    ItemDef('machado', 'Machado', TOOL, 'Corta árvores.', price=35, max_stack=1,
            damage=4, swing_time=0.55, tool=AXE, model='axe', icon_color=color.rgb32(170, 120, 70)),
    ItemDef('foice', 'Foice', TOOL, 'Colhe plantas e ervas.', price=25, max_stack=1,
            damage=3, swing_time=0.5, tool=SCYTHE, model='scythe', icon_color=color.rgb32(120, 170, 90)),

    # --------------------------------------------------------------- armas
    ItemDef('espada_madeira', 'Espada de Madeira', WEAPON, 'Melhor que nada.', max_stack=1,
            damage=5, reach=2.6, swing_time=0.5, model='wood_sword', icon_color=color.rgb32(196, 150, 96)),
    ItemDef('espada_pedra', 'Espada de Pedra', WEAPON, 'Pesada e afiada.', max_stack=1,
            damage=9, reach=2.7, swing_time=0.5, model='stone_sword', icon_color=color.rgb32(150, 150, 155)),
    ItemDef('martelo_pedra', 'Martelo de Pedra', WEAPON, 'Lento, mas devastador.', max_stack=1,
            damage=15, reach=2.9, swing_time=0.75, model='stone_hammer', icon_color=color.rgb32(115, 115, 125)),

    # ----------------------------------------------------------- materiais
    ItemDef('madeira', 'Madeira', MATERIAL, 'Obtida cortando árvores.', max_stack=999,
            icon_color=color.rgb32(140, 96, 60)),
    ItemDef('pedra', 'Pedra', MATERIAL, 'Obtida quebrando rochas.', max_stack=999,
            icon_color=color.rgb32(140, 140, 148)),
    ItemDef('ervas', 'Ervas', MATERIAL, 'Obtidas colhendo plantas.', max_stack=999,
            icon_color=color.rgb32(90, 170, 80)),
)


@dataclass(frozen=True)
class Recipe:
    result: str
    cost: dict = field(default_factory=dict)   # item_id -> quantidade


RECIPES = [
    Recipe('espada_pedra', {'madeira': 4, 'pedra': 8}),
    Recipe('martelo_pedra', {'madeira': 6, 'pedra': 14}),
]


def item(item_id):
    return ITEMS[item_id]
