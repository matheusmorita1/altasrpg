"""Interface: barras de vida/XP/fome, moedas, barra de itens, mensagens e numeros de dano."""
from ursina import Entity, Quad, Text, camera, color, curve, destroy, time, window, Vec3

from catalog import FOOD
from models import destroy_tree
from settings import MAX_HUNGER

HUNGER_COLOR = color.rgb32(235, 150, 50)


class Bar(Entity):
    """Barra horizontal simples (fundo + preenchimento + texto)."""

    def __init__(self, fill_color, width=0.42, height=0.03, **kwargs):
        kwargs.setdefault('parent', camera.ui)
        super().__init__(**kwargs)
        self.width = width
        Entity(parent=self, model='quad', origin=(-0.5, 0.5), scale=(width + 0.008, height + 0.008),
               position=(-0.004, 0.004), color=color.black66)
        self.fill = Entity(parent=self, model='quad', origin=(-0.5, 0.5), scale=(width, height),
                           z=-0.01, color=fill_color)
        self.label = Text(parent=self, x=0.008, y=-height / 2, z=-0.02, origin=(-0.5, 0), scale=0.8, text='')

    def set(self, value, maximum, label):
        ratio = max(0.0, min(1.0, value / maximum)) if maximum else 0
        self.fill.animate_scale_x(self.width * ratio, duration=0.15, curve=curve.out_quad)
        self.label.text = label


class HUD(Entity):
    def __init__(self):
        super().__init__(parent=camera.ui)
        left = window.top_left.x + 0.03
        right = window.top_right.x - 0.03
        top = 0.47
        # paineis escuros atras dos textos (legibilidade contra o ceu)
        Entity(parent=self, model='quad', origin=(-0.5, 0.5), position=(left - 0.015, top + 0.015, 0.5),
               scale=(0.465, 0.17), color=color.rgba(0, 0, 0, 0.35))
        Entity(parent=self, model='quad', origin=(0.5, 0.5), position=(right + 0.015, top + 0.015, 0.5),
               scale=(0.48, 0.17), color=color.rgba(0, 0, 0, 0.35))
        Entity(parent=self, model='quad', origin=(0, 0.5), position=(0, top + 0.015, 0.5),
               scale=(0.3, 0.05), color=color.rgba(0, 0, 0, 0.35))      # nome da area
        self.level_text = Text(parent=self, position=(left, top), origin=(-0.5, 0.5), scale=1.3,
                               text='Nível 1', color=color.rgb32(255, 230, 140))
        self.hp_bar = Bar(color.rgb32(210, 50, 50), parent=self, position=(left, top - 0.05))
        self.xp_bar = Bar(color.rgb32(70, 140, 230), height=0.018, parent=self, position=(left, top - 0.095))
        self.hunger_bar = Bar(HUNGER_COLOR, height=0.022, parent=self, position=(left, top - 0.125))

        self.coins_text = Text(parent=self, position=(right, top), origin=(0.5, 0.5), scale=1.2,
                               color=color.rgb32(255, 210, 60))
        self.potions_text = Text(parent=self, position=(right, top - 0.045), origin=(0.5, 0.5), scale=1.0,
                                 color=color.rgb32(255, 120, 140))
        self.food_text = Text(parent=self, position=(right, top - 0.08), origin=(0.5, 0.5), scale=1.0,
                              color=color.rgb32(255, 190, 110))
        self.materials_text = Text(parent=self, position=(right, top - 0.115), origin=(0.5, 0.5), scale=0.9,
                                   color=color.rgb32(210, 200, 180))
        self.objective_text = Text(parent=self, position=(left, top - 0.175), origin=(-0.5, 0.5), scale=0.9,
                                   color=color.rgb32(255, 225, 150), text=' ', wordwrap=38)  # (vazio quebra o wordwrap)
        self.zone_text = Text(parent=self, position=(0, top - 0.01), origin=(0, 0.5), scale=1.0,
                              color=color.rgb32(230, 230, 230))

        self.message = Text(parent=self, position=(0, 0.2), origin=(0, 0), scale=2.2, text='', alpha=0)
        self.sub_message = Text(parent=self, position=(0, 0.15), origin=(0, 0), scale=1.2, text='', alpha=0)

        self.controls = Text(
            parent=self, position=(0, top - 0.06), origin=(0, 0.5), scale=0.85, color=color.rgb32(40, 50, 70),
            text='WASD mover | Mouse câmera | Clique atacar/usar | Shift correr | Espaço pular\n'
                 '1-6 trocar item | C comer | E poção | F falar | Tab inventário | M música | Esc pausar')
        self.controls.animate('alpha', 0, duration=2, delay=25)

        # parte de baixo: aviso rapido, dica de interacao, item equipado e barra de itens
        self.notice = Text(parent=self, position=(0, -0.27), origin=(0, 0), scale=1.1, text='', alpha=0)
        self.prompt = Text(parent=self, position=(0, -0.32), origin=(0, 0), scale=1.15, text='',
                           color=color.rgb32(255, 240, 180))
        self.equipped_text = Text(parent=self, position=(0, -0.38), origin=(0, 0), scale=1.0,
                                  color=color.rgb32(230, 220, 200))
        self.hotbar = Entity(parent=self, y=-0.44)
        self._hotbar_key = None

        # vinheta vermelha quando toma dano
        self.damage_flash = Entity(parent=self, model='quad', texture='vignette', scale=(window.aspect_ratio, 1),
                                   color=color.rgba(1, 0, 0, 0), z=1)

    def refresh(self, player):
        inv = player.inventory
        self.level_text.text = f'Nível {player.level}'
        self.hp_bar.set(player.hp, player.max_hp, f'Vida {int(player.hp)}/{player.max_hp}')
        self.xp_bar.set(player.xp, player.xp_next, f'XP {player.xp}/{player.xp_next}')
        self.hunger_bar.set(player.hunger, MAX_HUNGER, f'Fome {int(player.hunger)}/{MAX_HUNGER}')
        self.hunger_bar.fill.color = HUNGER_COLOR if player.hunger > 25 else color.rgb32(220, 70, 40)
        self.coins_text.text = f'Moedas: {player.coins}'
        potions = inv.count('pocao_vida') + inv.count('pocao_grande')
        self.potions_text.text = f'Poções: {potions}  [E]'
        foods = sum(inv.count(f.id) for f in inv.items_of(FOOD))
        self.food_text.text = f'Comida: {foods}  [C]'
        self.materials_text.text = (f'Madeira {inv.count("madeira")}   Pedra {inv.count("pedra")}   '
                                    f'Ervas {inv.count("ervas")}')
        self.equipped_text.text = f'{player.equipped.name}  (dano {player.attack_damage_range()})'
        self._refresh_hotbar(player)

    def _refresh_hotbar(self, player):
        items = player.inventory.equippables()
        key = (tuple(i.id for i in items), player.equipped.id)
        if key == self._hotbar_key:
            return
        self._hotbar_key = key
        for child in list(self.hotbar.children):
            destroy_tree(child)
        size, gap = 0.075, 0.085
        x0 = -(len(items) - 1) * gap / 2
        for n, it in enumerate(items):
            selected = it.id == player.equipped.id
            slot = Entity(parent=self.hotbar, x=x0 + n * gap)
            Entity(parent=slot, model=Quad(radius=0.15), scale=size + 0.01, z=0.02,
                   color=color.rgb32(255, 210, 60) if selected else color.rgba(0, 0, 0, 0.4))
            Entity(parent=slot, model=Quad(radius=0.15), scale=size, z=0.01, color=color.rgba(0.1, 0.1, 0.12, 0.85))
            Entity(parent=slot, model=Quad(radius=0.3), scale=size * 0.5, color=it.icon_color)
            Text(parent=slot, text=str(n + 1), position=(-size / 2 + 0.008, size / 2 - 0.006), origin=(-0.5, 0.5),
                 scale=0.8, z=-0.01)

    def set_objective(self, text):
        self.objective_text.text = f'Objetivo: {text}' if text else ''

    def set_prompt(self, text):
        if self.prompt.text != text:
            self.prompt.text = text

    def notify(self, text, duration=2.0):
        """Aviso curto na parte de baixo da tela."""
        self.notice.text = text
        self.notice.alpha = 1
        self.notice.animate('alpha', 0, duration=0.6, delay=duration, curve=curve.linear)

    def show_message(self, text, sub='', text_color=color.white, duration=2.5):
        for t, value in ((self.message, text), (self.sub_message, sub)):
            t.text = value
            t.color = text_color if t is self.message else color.rgb32(235, 235, 235)
            t.alpha = 1
            t.animate('alpha', 0, duration=0.8, delay=duration, curve=curve.linear)

    def flash_damage(self):
        self.damage_flash.color = color.rgba(1, 0, 0, 0.35)
        self.damage_flash.animate_color(color.rgba(1, 0, 0, 0), duration=0.5, curve=curve.linear)


class FloatingText(Entity):
    """Texto que sobe a partir de um ponto do mundo 3D (numeros de dano, +XP...)."""

    def __init__(self, world_position, text, text_color=color.white, scale=1.4, lifetime=0.9):
        super().__init__()
        self.anchor = Entity(position=Vec3(world_position))
        self.label = Text(parent=camera.ui, text=text, origin=(0, 0), scale=scale, color=text_color)
        self.lifetime = lifetime
        self.age = 0
        self.anchor.x += (hash(id(self)) % 100 - 50) / 120   # pequeno espalhamento
        self._place()

    def _place(self):
        to_point = self.anchor.world_position - camera.world_position
        behind = to_point.dot(camera.forward) < 0
        self.label.enabled = not behind
        if not behind:
            self.label.position = self.anchor.screen_position

    def update(self):
        self.age += time.dt
        self.anchor.y += time.dt * 1.6
        self._place()
        t = self.age / self.lifetime
        if t > 0.6:
            self.label.alpha = max(0, 1 - (t - 0.6) / 0.4)
        if t >= 1:
            destroy(self.label)
            destroy(self.anchor)
            destroy(self)


class Overlay(Entity):
    """Tela de pausa / game over."""

    def __init__(self, title, subtitle, title_color=color.white):
        super().__init__(parent=camera.ui, model='quad', scale=(window.aspect_ratio * 1.1, 1.1),
                         color=color.rgba(0, 0, 0, 0.6), z=-1, enabled=False, ignore_paused=True)
        self.title = Text(parent=camera.ui, text=title, origin=(0, 0), y=0.08, scale=3.2, color=title_color,
                          z=-2, enabled=False, ignore_paused=True)
        self.subtitle = Text(parent=camera.ui, text=subtitle, origin=(0, 0), y=-0.04, scale=1.3,
                             z=-2, enabled=False, ignore_paused=True)

    def show(self, subtitle=None):
        if subtitle is not None:
            self.subtitle.text = subtitle
        self.enabled = self.title.enabled = self.subtitle.enabled = True

    def hide(self):
        self.enabled = self.title.enabled = self.subtitle.enabled = False
