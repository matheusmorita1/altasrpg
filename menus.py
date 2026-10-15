"""Menus clicaveis: lojas (comprar / fabricar) e inventario."""
from ursina import Button, Entity, Quad, Text, camera, color

from catalog import FOOD, ITEMS, MATERIAL, POTION, RECIPES, TOOL, WEAPON
from models import destroy_tree
import sounds

PANEL = color.rgba(0.07, 0.06, 0.09, 0.93)
ROW_BG = color.rgba(1, 1, 1, 0.05)
GOLD = color.rgb32(255, 210, 60)
GRAY = color.rgb32(170, 170, 170)
OK_GREEN = color.rgb32(60, 150, 70)
BAD_RED = color.rgb32(140, 60, 60)
DISABLED = color.rgb32(80, 80, 80)


class Menu(Entity):
    """Painel central. O conteudo e reconstruido a cada refresh()."""

    def __init__(self, game, title, width=1.25, height=0.88):
        super().__init__(parent=camera.ui, enabled=False, z=-5)
        self.game = game
        self.width, self.height = width, height
        Entity(parent=self, model=Quad(radius=0.02), scale=(width, height), color=PANEL, z=0.02)
        self.title = Text(parent=self, text=title, position=(0, height / 2 - 0.045), origin=(0, 0), scale=1.7,
                          color=GOLD)
        Button(parent=self, text='Fechar (Esc)', scale=(0.16, 0.04), position=(width / 2 - 0.1, height / 2 - 0.04),
               color=color.rgb32(110, 50, 50), on_click=self.game.close_menu)
        self.feedback = Text(parent=self, text='', position=(0, -height / 2 + 0.035), origin=(0, 0), scale=1.0)
        self.content = None

    def open(self):
        self.enabled = True
        self.feedback.text = ''
        self.refresh()

    def close(self):
        self.enabled = False

    def refresh(self):
        if self.content:
            destroy_tree(self.content)
        self.content = Entity(parent=self)
        self.build(self.content)

    def build(self, root):
        pass

    def say(self, text, good=True):
        self.feedback.text = text
        self.feedback.color = color.rgb32(150, 230, 140) if good else color.rgb32(255, 120, 110)
        if not good:
            sounds.error()

    # ------------------------------------------------------------ helpers
    def heading(self, root, text, x, y):
        Text(parent=root, text=text, position=(x, y), origin=(-0.5, 0), scale=1.15, color=color.rgb32(230, 200, 140))

    def item_row(self, root, item, x, y, width, info='', info_color=GRAY, button=None, on_click=None,
                 button_color=OK_GREEN):
        """Linha: icone | nome + descricao | info (preco/qtd) | botao."""
        Entity(parent=root, model=Quad(radius=0.15), origin=(-0.5, 0), position=(x, y, 0.01),
               scale=(width, 0.072), color=ROW_BG)
        Entity(parent=root, model=Quad(radius=0.25), position=(x + 0.04, y), scale=0.048, color=item.icon_color)
        Text(parent=root, text=item.name, position=(x + 0.08, y + 0.013), origin=(-0.5, 0), scale=1.05)
        Text(parent=root, text=item.description, position=(x + 0.08, y - 0.017), origin=(-0.5, 0), scale=0.78,
             color=GRAY)
        bx = x + width - 0.09
        if info:
            Text(parent=root, text=info, position=(bx - 0.105, y), origin=(0.5, 0), scale=0.95, color=info_color)
        if button:
            b = Button(parent=root, text=button, scale=(0.15, 0.045), position=(bx, y), color=button_color)
            if on_click:
                b.on_click = on_click


def stats_line(item):
    """Resumo dos efeitos de um item, para mostrar nas lojas."""
    parts = []
    if item.heal:
        parts.append(f'+{item.heal} vida')
    if item.heal_ratio:
        parts.append(f'+{int(item.heal_ratio * 100)}% vida')
    if item.hunger:
        parts.append(f'+{item.hunger} fome')
    if item.kind in (WEAPON, TOOL):
        parts.append(f'dano {item.damage}')
    return '  '.join(parts)


# ===================================================================== loja
class ShopMenu(Menu):
    def __init__(self, game, shop):
        super().__init__(game, shop.title)
        self.shop = shop

    def build(self, root):
        p = self.game.player
        top = self.height / 2
        left = -self.width / 2 + 0.04
        row_w = self.width - 0.08
        Text(parent=root, text=f'{self.shop.vendor}: "{self.shop.greeting}"', position=(0, top - 0.1),
             origin=(0, 0), scale=0.95, color=color.rgb32(220, 220, 220), wordwrap=70)
        Text(parent=root, text=f'Suas moedas: {p.coins}', position=(0, top - 0.15), origin=(0, 0), scale=1.15,
             color=GOLD)

        y = top - 0.23
        self.heading(root, 'À venda', left, y)
        y -= 0.06
        for item_id in self.shop.stock:
            it = ITEMS[item_id]
            owned = p.inventory.count(item_id)
            if it.max_stack == 1 and owned:
                label, col, action = 'Já possui', DISABLED, None
            else:
                affordable = p.coins >= it.price
                label, col = 'Comprar', OK_GREEN if affordable else BAD_RED
                action = lambda i=item_id: self.buy(i)  # noqa: E731
            info = f'{it.price} moedas'
            if it.max_stack > 1:
                info = f'tem {owned}   ' + info
            self.item_row(root, it, left, y, row_w, info=f'{stats_line(it)}    {info}',
                          button=label, on_click=action, button_color=col)
            y -= 0.082

        if self.shop.crafting:
            y -= 0.02
            self.heading(root, 'Fabricar armas (com seus materiais)', left, y)
            y -= 0.06
            for recipe in RECIPES:
                it = ITEMS[recipe.result]
                owned = p.inventory.has(recipe.result)
                cost = '  '.join(f'{ITEMS[i].name} {p.inventory.count(i)}/{n}' for i, n in recipe.cost.items())
                can = p.inventory.has_all(recipe.cost)
                if owned:
                    label, col, action = 'Já possui', DISABLED, None
                else:
                    label, col = 'Fabricar', OK_GREEN if can else BAD_RED
                    action = lambda r=recipe: self.craft(r)  # noqa: E731
                self.item_row(root, it, left, y, row_w, info=f'{stats_line(it)}    {cost}',
                              info_color=color.rgb32(150, 230, 140) if can else GRAY,
                              button=label, on_click=action, button_color=col)
                y -= 0.082

    def buy(self, item_id):
        p = self.game.player
        it = ITEMS[item_id]
        if p.inventory.space_for(item_id) <= 0:
            self.say(f'Você não consegue carregar mais {it.name}.', good=False)
        elif not p.spend_coins(it.price):
            self.say(f'Moedas insuficientes: {it.name} custa {it.price}.', good=False)
        else:
            p.inventory.add(item_id)
            sounds.buy()
            hint = ''
            if it.equippable:
                slot = [e.id for e in p.inventory.equippables()].index(item_id) + 1
                hint = f'  Aperte {slot} para equipar.'
            elif it.kind == FOOD:
                hint = '  Coma com C.'
            elif it.kind == POTION:
                hint = '  Beba com E.'
            self.say(f'Você comprou {it.name}!{hint}')
        self.refresh()

    def craft(self, recipe):
        p = self.game.player
        it = ITEMS[recipe.result]
        if not p.inventory.remove_all(recipe.cost):
            self.say(f'Faltam materiais para {it.name}.', good=False)
        else:
            p.inventory.add(recipe.result)
            p.equip(recipe.result)
            sounds.craft()
            self.say(f'{it.name} fabricada e equipada! Dano {it.damage}.')
        self.refresh()


# =============================================================== inventario
class InventoryMenu(Menu):
    def __init__(self, game):
        super().__init__(game, 'Inventário', width=1.5)

    def build(self, root):
        p = self.game.player
        top = self.height / 2
        Text(parent=root, position=(0, top - 0.1), origin=(0, 0), scale=1.0,
             text=f'Vida {int(p.hp)}/{p.max_hp}     Fome {int(p.hunger)}/100     Nível {p.level}     '
                  f'Moedas {p.coins}')

        col_w = self.width / 2 - 0.06
        left = -self.width / 2 + 0.04
        right = 0.02
        y0 = top - 0.18

        self.heading(root, 'Consumíveis', left, y0)
        y = y0 - 0.06
        consumables = p.inventory.items_of(FOOD, POTION)
        if not consumables:
            Text(parent=root, text='Nada para comer ou beber.', position=(left, y), origin=(-0.5, 0), scale=0.9,
                 color=GRAY)
        for it in consumables:
            self.item_row(root, it, left, y, col_w, info=f'x{p.inventory.count(it.id)}',
                          button='Usar', on_click=lambda i=it.id: self.use(i))
            y -= 0.082

        self.heading(root, 'Equipamentos', right, y0)
        y = y0 - 0.06
        for n, it in enumerate(p.inventory.equippables(), start=1):
            equipped = p.equipped.id == it.id
            self.item_row(root, it, right, y, col_w, info=f'[{n}]  dano {it.damage}',
                          button='Equipado' if equipped else 'Equipar',
                          on_click=None if equipped else (lambda i=it.id: self.equip(i)),
                          button_color=DISABLED if equipped else OK_GREEN)
            y -= 0.082

        mats = p.inventory.items_of(MATERIAL)
        text = '   '.join(f'{m.name}: {p.inventory.count(m.id)}' for m in mats) or 'nenhum ainda'
        self.heading(root, 'Materiais', left, -top + 0.13)
        Text(parent=root, text=text, position=(left, -top + 0.08), origin=(-0.5, 0), scale=1.0)

    def use(self, item_id):
        if self.game.player.consume(item_id):
            self.say(f'Você usou {ITEMS[item_id].name}.')
        self.refresh()

    def equip(self, item_id):
        self.game.player.equip(item_id)
        self.say(f'{ITEMS[item_id].name} equipado.')
        self.refresh()


# ============================================================ tela inicial
class TitleScreen(Entity):
    """Primeira tela: Continuar (se houver save) / Novo jogo / Sair."""

    def __init__(self, game, save_summary=None, save_problem=None):
        super().__init__(parent=camera.ui, z=-8, ignore_paused=True)   # o jogo fica pausado atras
        self.game = game
        self.confirming_new = False
        Entity(parent=self, model='quad', scale=(4, 2), color=color.rgba(0.05, 0.07, 0.1, 0.55), z=0.05)
        Text(parent=self, text='Lâmina de Carvalho', position=(0, 0.25), origin=(0, 0), scale=4, color=GOLD)
        Text(parent=self, text='um RPG 3D feito em Python', position=(0, 0.17), origin=(0, 0), scale=1.2,
             color=color.rgb32(220, 220, 220))

        y = 0.04
        if save_summary:
            Button(parent=self, text='Continuar', scale=(0.34, 0.07), position=(0, y), color=OK_GREEN,
                   on_click=self.game.continue_game)
            Text(parent=self, text=save_summary, position=(0, y - 0.06), origin=(0, 0), scale=0.9, color=GRAY)
            y -= 0.15
        elif save_problem:
            Text(parent=self, text=f'Não foi possível ler o save: {save_problem}', position=(0, y),
                 origin=(0, 0), scale=0.9, color=color.rgb32(255, 120, 110), wordwrap=80)
            y -= 0.09
        self.has_save = bool(save_summary)
        self.new_button = Button(parent=self, text='Novo jogo', scale=(0.34, 0.07), position=(0, y),
                                 color=color.rgb32(70, 110, 160), on_click=self.new_game)
        self.warning = Text(parent=self, text='', position=(0, y - 0.06), origin=(0, 0), scale=0.9,
                            color=color.rgb32(255, 170, 110))
        Button(parent=self, text='Sair', scale=(0.34, 0.06), position=(0, y - 0.15),
               color=color.rgb32(110, 50, 50), on_click=self.game.quit_game)
        Text(parent=self, text='Enter = ' + ('Continuar' if save_summary else 'Novo jogo'),
             position=(0, -0.4), origin=(0, 0), scale=0.9, color=GRAY)

    def new_game(self):
        if self.has_save and not self.confirming_new:
            # pede confirmacao para nao apagar o progresso sem querer
            self.confirming_new = True
            self.new_button.text = 'Confirmar novo jogo'
            self.new_button.color = BAD_RED
            self.warning.text = 'O progresso salvo será substituído. Clique de novo para confirmar.'
            return
        self.game.start_new_game()

    def input(self, key):
        if key == 'enter':
            if self.has_save:
                self.game.continue_game()
            else:
                self.game.start_new_game()
