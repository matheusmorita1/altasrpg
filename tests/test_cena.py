"""Teste da cena de abertura: toca a cutscene numa janela (2x mais rapido), tira screenshots
ao longo dela e confere se o jogo termina no estado certo. Depois testa pular a cena (Esc).

Uso (de dentro da pasta rpg3d):
    python tests/test_cena.py
"""
import os
import sys
import tempfile

GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(GAME_DIR, 'tests', 'screenshots')
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, GAME_DIR)
os.chdir(GAME_DIR)

from panda3d.core import Filename
from ursina import Entity, Ursina, Vec3, application, camera, time, window

app = Ursina(development_mode=False, size=(1280, 720))
window.fps_counter.enabled = False

import save  # noqa: E402
save.use_directory(tempfile.mkdtemp(prefix='rpg3d_save_'))
from game import Game  # noqa: E402
from settings import PLAYER_SPAWN  # noqa: E402
import story  # noqa: E402

game = Game(show_title=True)
p = game.player
problems = []
results = []
SPEED = 2.0


def check(ok, msg):
    results.append(('  OK    ' if ok else '  FALHA ') + msg)
    if not ok:
        problems.append(msg)


def shot(name):
    app.win.saveScreenshot(Filename.fromOsSpecific(os.path.join(OUT, name)))


class Director(Entity):
    """Inicia a cena, fotografa, e depois testa o 'pular'."""

    def __init__(self):
        super().__init__(ignore_paused=True)
        self.t = 0.0
        self.phase = 'wait_title'
        self.next_shot = 0.5
        self.n = 0

    def update(self):
        dt = time.dt_unscaled
        self.t += dt
        if self.phase == 'wait_title' and self.t > 1.5:
            shot('cena_00_titulo.png')
            game.title.new_game()
            application.time_scale = SPEED
            self.phase, self.t = 'intro', 0.0
        elif self.phase == 'intro':
            scene_time = self.t * SPEED
            if game.cutscene and scene_time >= self.next_shot:
                self.n += 1
                shot(f'cena_{self.n:02d}.png')
                self.next_shot += 2.5
            if game.cutscene is None:
                application.time_scale = 1
                print(f'cena durou ~{scene_time:.0f} s (em tempo de jogo)')
                self.check_end('fim normal')
                self.phase, self.t = 'after', 0.0
        elif self.phase == 'after' and self.t > 1.0:
            shot('cena_fim_jogo.png')
            # agora: pular a cena com Esc
            game.intro_done = False
            story.play_intro(game, on_done=game._after_intro)
            self.phase, self.t = 'skip', 0.0
        elif self.phase == 'skip' and self.t > 3.0:
            game.cutscene.input('escape')
            self.phase, self.t = 'after_skip', 0.0
        elif self.phase == 'after_skip' and self.t > 0.5:
            self.check_end('depois de pular')
            for line in results:
                print(line)
            print('Problemas: ' + ('; '.join(problems) if problems else 'nenhum'))
            application.quit()

    def check_end(self, label):
        check(game.cutscene is None, f'{label}: cena terminou')
        check(not game.blocked, f'{label}: jogador tem o controle')
        check((p.position - Vec3(*PLAYER_SPAWN)).length() < 4 and p.y > -1,
              f'{label}: Arthur na porta de casa ({p.x:.1f}, {p.z:.1f})')
        check(abs(p.body.rotation_x) < 1 and p.held.enabled, f'{label}: Arthur de pe e com a espada')
        check(camera.parent == p.cam_pivot, f'{label}: camera voltou para tras do heroi')
        check(game.objective == story.INTRO_OBJECTIVE, f'{label}: objetivo definido')
        check(game.daylight < 0.3 and game._dawn_speed > 0, f'{label}: ainda e noite e o dia esta nascendo')
        check(game.hud.enabled, f'{label}: HUD visivel')
        check(save.SAVE_FILE.exists(), f'{label}: jogo salvo ao fim da cena')
        check(any(not e.dormant for e in game.enemies), f'{label}: monstros acordaram')


Director()
app.run()
