"""Lamina de Carvalho - um RPG 3D feito em Python com Ursina.

Execute:  python main.py
"""
from ursina import Ursina, window

from settings import WINDOW_TITLE

app = Ursina(title=WINDOW_TITLE, development_mode=False)
window.fps_counter.enabled = True
window.exit_button.visible = False

from game import Game  # noqa: E402  (precisa da janela criada antes)

game = Game()
app.run()
