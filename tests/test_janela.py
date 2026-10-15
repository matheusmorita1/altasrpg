"""Teste visual: abre o jogo numa janela de verdade, joga sozinho por ~15 segundos,
tira screenshots (HUD, lojas, coleta, inventario, combate) e fecha.
Mostra o FPS medio e os problemas encontrados no final.

Uso (de dentro da pasta rpg3d):
    python tests/test_janela.py
Nao mexa no mouse enquanto ele roda.
"""
import math
import os
import sys

GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(GAME_DIR, 'tests', 'screenshots')
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, GAME_DIR)
os.chdir(GAME_DIR)

from panda3d.core import Filename
from ursina import Entity, Ursina, Vec3, application, color, distance_xz, time, window

from settings import WINDOW_TITLE

app = Ursina(title=WINDOW_TITLE, development_mode=False, size=(1280, 720))
window.color = color.rgb32(170, 210, 255)
window.fps_counter.enabled = True
window.exit_button.visible = False

import tempfile  # noqa: E402
import save  # noqa: E402
save.use_directory(tempfile.mkdtemp(prefix='rpg3d_save_'))   # nunca mexe no seu save de verdade
from game import Game  # noqa: E402
from world import SHOP_SPOTS, facing_center  # noqa: E402
game = Game()
p = game.player
problems = []
fps_samples = []


def shot(name):
    app.win.saveScreenshot(Filename.fromOsSpecific(os.path.join(OUT, name)))


def go_to_shop(kind):
    x, z = SHOP_SPOTS[kind]
    yaw = facing_center(x, z)
    p.position = Vec3(x + math.sin(math.radians(yaw)) * 2.8, 0, z + math.cos(math.radians(yaw)) * 2.8)
    p.cam_pivot.rotation_y = yaw + 180


def open_shop(kind):
    game.input('f')
    if game.menu is not game.shop_menus[kind]:
        problems.append(f'loja {kind} nao abriu com F')


def go_to_meadow():
    p.position = Vec3(-24, 0, -18)


def attack_nearest():
    target = min((e for e in game.enemies if not e.dead), key=lambda e: distance_xz(e, p))
    p.position = target.position + Vec3(1.5, 0, 0)
    p.cam_pivot.rotation_y = -90
    p.start_attack()


def chop_tree():
    node = next(n for n in game.world.nodes if n.kind == 'tree' and not n.depleted and math.hypot(n.x, n.z) > 22)
    p.position = Vec3(node.x - node.radius - 1.0, 0, node.z)
    p.rotation_y = 90
    p.cam_pivot.rotation_y = 90
    p.start_attack()


def check_saved():
    if not save.SAVE_FILE.exists():
        problems.append('G na pausa nao salvou')


def finish():
    fps = sorted(fps_samples)[len(fps_samples) // 2] if fps_samples else 0
    print(f'FPS medio: {fps:.0f}')
    print('Problemas: ' + ('; '.join(problems) if problems else 'nenhum'))
    print(f'Screenshots em: {OUT}')
    application.quit()


# (segundos de espera ANTES do passo, funcao, argumentos)
STEPS = [
    (2.0, shot, 'janela_00_tela_inicial.png'),
    (0.1, lambda: game.start_new_game(intro=False)),   # a cena de abertura tem teste proprio (test_cena.py)
    (0.1, game.set_daylight, 1.0),
    (1.5, shot, 'janela_01_inicio.png'),
    (0.1, go_to_shop, 'food'),
    (0.5, shot, 'janela_02_frente_loja.png'),
    (0.1, open_shop, 'food'),
    (0.2, game.shop_menus['food'].buy, 'maca'),
    (0.3, shot, 'janela_03_loja_alimentos.png'),
    (0.1, game.close_menu),
    (0.1, go_to_shop, 'smith'),
    (0.3, open_shop, 'smith'),
    (0.2, game.shop_menus['smith'].buy, 'machado'),
    (0.3, shot, 'janela_04_ferraria.png'),
    (0.1, game.close_menu),
    (0.1, go_to_shop, 'witch'),
    (0.3, open_shop, 'witch'),
    (0.3, shot, 'janela_05_bruxaria.png'),
    (0.1, game.close_menu),
    (0.2, p.equip, 'machado'),
    (0.3, chop_tree),
    (0.25, shot, 'janela_06_cortando.png'),
    (0.4, chop_tree),
    (0.6, chop_tree),
    (0.6, chop_tree),
    (0.8, game.input, 'tab'),
    (0.3, shot, 'janela_07_inventario.png'),
    (0.1, game.close_menu),
    (0.1, p.equip, 'espada_madeira'),
    (0.1, go_to_meadow),
    (0.6, attack_nearest),
    (0.35, shot, 'janela_08_combate.png'),
    (0.3, attack_nearest),
    (0.6, attack_nearest),
    (0.5, game.toggle_pause),
    (0.2, game.input, 'g'),
    (0.3, shot, 'janela_09_pausa_salvo.png'),
    (0.1, check_saved),
    (0.3, finish),
]


class StepRunner(Entity):
    """Executa os passos em ordem; funciona mesmo com o jogo pausado (menus abertos)."""

    def __init__(self):
        super().__init__(ignore_paused=True)
        self.index = 0
        self.wait = STEPS[0][0]

    def update(self):
        fps_samples.append(1 / max(time.dt_unscaled, 1e-6))
        self.wait -= time.dt_unscaled
        if self.wait > 0 or self.index >= len(STEPS):
            return
        _, func, *args = STEPS[self.index]
        func(*args)
        self.index += 1
        if self.index < len(STEPS):
            self.wait = STEPS[self.index][0]


p.coins = 200
p.inventory.add('madeira', 6)
p.inventory.add('pedra', 10)
StepRunner()
app.run()
