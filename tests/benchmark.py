"""Mede o desempenho do jogo numa janela real: tempo de frame, quanto vai para o Python
(logica/entidades) e quanto vai para a renderizacao, em tres pontos do mapa.

Uso (de dentro da pasta rpg3d):
    python tests/benchmark.py
"""
import os
import sys
import time as pytime

GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GAME_DIR)
os.chdir(GAME_DIR)

from panda3d.core import loadPrcFileData
loadPrcFileData('', 'sync-video false')   # sem vsync, para medir o custo real

from ursina import Entity, Ursina, Vec3, application, scene, window
from ursina import main as ursina_main

app = Ursina(development_mode=False, size=(1280, 720))
window.fps_counter.enabled = False

import tempfile  # noqa: E402
import save  # noqa: E402
save.use_directory(tempfile.mkdtemp(prefix='rpg3d_save_'))   # nunca mexe no seu save de verdade
from game import Game  # noqa: E402
game = Game(show_title=False)
p = game.player

# cronometra o loop de entidades do Ursina e o desenho separadamente
timings = {'update': 0.0, 'render': 0.0}
_orig_update = app._update


def timed_update(task=None):
    t = pytime.perf_counter()
    r = _orig_update(task)
    timings['update'] += pytime.perf_counter() - t
    return r


app.taskMgr.remove('update')
app.taskMgr.add(timed_update, 'update')
_orig_render = app.graphicsEngine.renderFrame


SPOTS = [('vila', Vec3(-9, 0, -7.2), -128), ('campina', Vec3(-22, 0, -16), 225), ('floresta', Vec3(40, 0, -40), 0)]
results = []


def measure(name, frames=240):
    timings['update'] = 0.0
    t0 = pytime.perf_counter()
    for _ in range(frames):
        t = pytime.perf_counter()
        app.taskMgr.step()
        timings['render'] += 0
    total = (pytime.perf_counter() - t0) / frames * 1000
    upd = timings['update'] / frames * 1000
    results.append((name, total, upd, total - upd))


for _ in range(60):
    app.taskMgr.step()
for name, pos, yaw in SPOTS:
    p.position = pos
    p.cam_pivot.rotation_y = yaw
    for _ in range(30):
        app.taskMgr.step()
    measure(name)

active = sum(1 for e in scene.entities if e.enabled and not e.ignore)
print(f'entidades na cena: {len(scene.entities)}  (ativas: {active})')
print(f'{"local":10} {"frame ms":>9} {"FPS":>6} {"python ms":>10} {"render ms":>10}')
for name, total, upd, rest in results:
    print(f'{name:10} {total:9.1f} {1000 / total:6.0f} {upd:10.1f} {rest:10.1f}')
application.quit()
