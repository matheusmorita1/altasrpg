"""Efeitos sonoros retro gerados na hora (sem arquivos de audio)."""
import random

from ursina.prefabs.ursfx import ursfx

ENABLED = True


def _play(*args, **kwargs):
    if not ENABLED:
        return
    # ignore_paused: os menus pausam o jogo, e sem isso o som nunca pararia de tocar
    kwargs.setdefault('ignore_paused', True)
    try:
        ursfx(*args, **kwargs)
    except Exception:
        pass   # sem dispositivo de audio: o jogo continua mudo


def swing():
    _play([(0.0, 0.0), (0.05, 0.6), (0.1, 0.3), (0.2, 0.1), (0.3, 0.0)],
          volume=0.35, wave='noise', pitch=random.uniform(18, 22), pitch_change=-10, speed=2.2)


def hit():
    _play([(0.0, 0.0), (0.02, 1.0), (0.08, 0.5), (0.2, 0.1), (0.3, 0.0)],
          volume=0.5, wave='square', pitch=random.uniform(-14, -10), pitch_change=-8, speed=2.5)


def crit():
    _play([(0.0, 0.0), (0.02, 1.0), (0.1, 0.6), (0.25, 0.2), (0.4, 0.0)],
          volume=0.55, wave='square', pitch=-4, pitch_change=-16, speed=2.0)


def hurt():
    _play([(0.0, 0.0), (0.03, 1.0), (0.1, 0.6), (0.25, 0.2), (0.4, 0.0)],
          volume=0.5, wave='triangle', pitch=-6, pitch_change=-14, speed=2.0)


def enemy_die():
    _play([(0.0, 0.0), (0.05, 0.8), (0.2, 0.5), (0.4, 0.2), (0.6, 0.0)],
          volume=0.45, wave='noise', pitch=-6, pitch_change=-20, speed=1.6)


def coin():
    _play([(0.0, 0.0), (0.02, 0.7), (0.06, 0.6), (0.15, 0.2), (0.25, 0.0)],
          volume=0.3, wave='sine', pitch=random.uniform(24, 27), pitch_change=7, speed=2.5,
          pitch_curve=lambda t: 0 if t < 0.4 else 1)


def potion():
    _play([(0.0, 0.0), (0.05, 0.6), (0.2, 0.5), (0.4, 0.2), (0.6, 0.0)],
          volume=0.35, wave='sine', pitch=8, pitch_change=12, speed=1.5)


def level_up():
    _play([(0.0, 0.0), (0.05, 0.8), (0.4, 0.7), (0.7, 0.3), (1.0, 0.0)],
          volume=0.45, wave='square', pitch=6, pitch_change=24, speed=1.0)


def jump():
    _play([(0.0, 0.0), (0.03, 0.5), (0.08, 0.3), (0.15, 0.1), (0.2, 0.0)],
          volume=0.2, wave='sine', pitch=4, pitch_change=10, speed=2.5)


def eat():
    _play([(0.0, 0.0), (0.03, 0.7), (0.08, 0.2), (0.12, 0.6), (0.25, 0.0)],
          volume=0.35, wave='noise', pitch=random.uniform(8, 12), pitch_change=-4, speed=2.0)


def chop():
    _play([(0.0, 0.0), (0.01, 1.0), (0.05, 0.4), (0.15, 0.1), (0.25, 0.0)],
          volume=0.5, wave='noise', pitch=random.uniform(-4, 0), pitch_change=-10, speed=2.5)


def mine():
    _play([(0.0, 0.0), (0.01, 1.0), (0.04, 0.5), (0.12, 0.2), (0.3, 0.0)],
          volume=0.45, wave='square', pitch=random.uniform(14, 18), pitch_change=-6, speed=2.5)


def harvest():
    _play([(0.0, 0.0), (0.03, 0.6), (0.1, 0.3), (0.2, 0.1), (0.3, 0.0)],
          volume=0.3, wave='noise', pitch=random.uniform(20, 24), pitch_change=6, speed=2.5)


def buy():
    _play([(0.0, 0.0), (0.02, 0.7), (0.1, 0.6), (0.2, 0.3), (0.35, 0.0)],
          volume=0.35, wave='sine', pitch=20, pitch_change=12, speed=1.8,
          pitch_curve=lambda t: 0 if t < 0.3 else 1)


def craft():
    _play([(0.0, 0.0), (0.01, 1.0), (0.1, 0.5), (0.3, 0.3), (0.6, 0.0)],
          volume=0.45, wave='square', pitch=10, pitch_change=-2, speed=1.4)


def error():
    _play([(0.0, 0.0), (0.02, 0.5), (0.1, 0.4), (0.15, 0.2), (0.2, 0.0)],
          volume=0.3, wave='square', pitch=-12, pitch_change=-2, speed=2.0)


def goblin_laugh():
    for i in range(3):
        _play([(0.0, 0.0), (0.02, 0.6), (0.06, 0.4), (0.09, 0.1), (0.12, 0.0)],
              volume=0.3, wave='square', pitch=random.uniform(14, 18) - i * 2, pitch_change=4, speed=1.6)


def door():
    _play([(0.0, 0.0), (0.01, 1.0), (0.06, 0.5), (0.2, 0.15), (0.4, 0.0)],
          volume=0.55, wave='noise', pitch=-18, pitch_change=-6, speed=1.4)
