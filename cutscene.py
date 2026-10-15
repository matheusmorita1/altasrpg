"""Motor de cutscenes: um roteiro escrito como uma sequencia de passos.

O roteiro e uma funcao geradora. Cada `yield` espera um passo terminar:

    def roteiro(cs):
        yield cs.fade(0, 1.5)                          # tela preta clareia em 1,5 s
        cs.go(cs.walk(pai, (18, 0, 8), speed=1.6))      # comeca a andar (sem esperar)
        yield cs.camera((10, 2.5, 3), look=pai)         # corta a camera
        yield cs.say('Edmundo', 'Que noite fria...')    # espera o jogador ler
        yield 2                                         # espera 2 segundos

Controles durante a cena: Espaco/Enter/clique avancam o dialogo, Esc pula a cena inteira.
"""
import math

from ursina import Entity, Text, Vec3, camera, color, curve, lerp, scene, time

from models import destroy_tree, part
from settings import C


# ================================================================ tarefas
class Task:
    """Algo que acontece ao longo de varios frames. step() devolve True quando termina."""
    done = False
    cancelled = False

    def step(self, dt):
        return True


class Wait(Task):
    def __init__(self, seconds):
        self.left = seconds

    def step(self, dt):
        self.left -= dt
        return self.left <= 0


class Call(Task):
    """Executa uma funcao a cada frame por `duration` segundos, com t indo de 0 a 1."""

    def __init__(self, func, duration):
        self.func, self.duration, self.t = func, max(duration, 1e-4), 0.0

    def step(self, dt):
        self.t = min(1.0, self.t + dt / self.duration)
        self.func(self.t)
        return self.t >= 1.0


class All(Task):
    def __init__(self, tasks):
        self.tasks = list(tasks)

    def step(self, dt):
        return all(t.done for t in self.tasks)


def smooth(t):
    return t * t * (3 - 2 * t)


def aim_camera(target):
    """Aponta a camera para um ponto SEM girar de lado (horizonte sempre reto).
    (O look_at do Ursina gira a partir da rotacao anterior e, chamado todo frame,
    vai acumulando inclinacao.)"""
    d = Vec3(*target) - camera.world_position
    if d.length() < 1e-5:
        return
    d = d.normalized()
    camera.rotation = (math.degrees(math.asin(max(-1.0, min(1.0, -d.y)))),
                       math.degrees(math.atan2(d.x, d.z)), 0)


# ================================================================ atores
class Actor(Entity):
    """Personagem de cena (sem IA): anda, vira, deita e anima pernas/bracos."""

    def __init__(self, position, shirt, pants, skin=C['skin'], hair=C['hair'], **kwargs):
        super().__init__(position=position, **kwargs)
        self.moving = False
        self.walk_t = 0.0
        self.speed_anim = 9
        self.body = Entity(parent=self)
        b = self.body
        self.legs = []
        for sx in (-0.14, 0.14):
            pivot = Entity(parent=b, position=(sx, 0.82, 0))
            part(parent=pivot, scale=(0.2, 0.8, 0.22), y=-0.4, color=pants)
            self.legs.append(pivot)
        part(parent=b, scale=(0.58, 0.65, 0.34), y=1.14, color=shirt)
        self.arms = []
        for sx in (-0.37, 0.37):
            pivot = Entity(parent=b, position=(sx, 1.42, 0))
            part(parent=pivot, scale=(0.16, 0.56, 0.18), y=-0.27, color=shirt.tint(-0.08))
            part(parent=pivot, scale=(0.14, 0.12, 0.16), y=-0.6, color=skin)
            self.arms.append(pivot)
        self.head = Entity(parent=b, y=1.7)
        part(parent=self.head, scale=0.42, color=skin)
        part(parent=self.head, scale=(0.46, 0.13, 0.46), y=0.2, color=hair)
        for sx in (-0.09, 0.09):
            part(parent=self.head, scale=(0.07, 0.08, 0.03), position=(sx, 0.02, 0.21), color=color.rgb32(30, 30, 40))

    def update(self):
        dt = time.dt
        if self.moving:
            self.walk_t += dt * self.speed_anim
            swing = math.sin(self.walk_t) * 35
        else:
            swing = lerp(self.legs[0].rotation_x, 0, min(1, dt * 10))
        self.legs[0].rotation_x = swing
        self.legs[1].rotation_x = -swing
        self.arms[0].rotation_x = -swing * 0.8
        self.arms[1].rotation_x = swing * 0.8


# ============================================================= cutscene
class Cutscene(Entity):
    """Executa um roteiro. `on_end(skipped)` e chamado no fim (ou ao pular)."""

    def __init__(self, game, script, on_end, finish):
        super().__init__(parent=camera.ui)
        self.game = game
        self.on_end = on_end
        self._finish_state = finish          # deixa o mundo no estado final (usado ao pular)
        self.tasks = []
        self.current = None
        self.ended = False
        self.dialogue = None
        self.actors = []                     # tudo criado so para a cena (apagado no fim)

        # faixas pretas de cinema
        # origin no lado de fora: a de cima cresce para baixo a partir da borda superior, e vice-versa
        self.bars = [Entity(parent=self, model='quad', color=color.black, origin=(0, oy), y=oy,
                            scale=(4, 0.0), z=-1) for oy in (0.5, -0.5)]
        for bar in self.bars:
            bar.animate_scale_y(0.11, duration=0.8, curve=curve.out_quad)
        # tela preta para fades (comeca preta)
        self.black = Entity(parent=self, model='quad', color=color.black, scale=(4, 2), z=-3)
        self.skip_hint = Text(parent=self, text='Esc: pular cena', position=(0.84, 0.47), origin=(0.5, 0.5),
                              scale=0.9, color=color.rgba(1, 1, 1, 0.6), z=-4)
        self.card = Text(parent=self, text='', position=(0, 0.05), origin=(0, 0), scale=2.6, z=-4,
                         color=color.rgb32(255, 220, 140))
        self.card_sub = Text(parent=self, text='', position=(0, -0.03), origin=(0, 0), scale=1.3, z=-4)

        self.saved_camera = (camera.parent, Vec3(camera.position), Vec3(camera.rotation), camera.fov)
        camera.parent = scene
        camera.fov = 58
        self._gen = script(self)

    # ------------------------------------------------------------- passos
    def go(self, task):
        """Comeca uma tarefa em paralelo (sem esperar por ela)."""
        if isinstance(task, (int, float)):
            task = Wait(task)
        self.tasks.append(task)
        return task

    def wait(self, seconds):
        return Wait(seconds)

    def cancel(self, *tasks):
        """Interrompe tarefas em andamento (ex.: alguem que ainda estava andando)."""
        for t in tasks:
            t.cancelled = True

    def all(self, *tasks):
        for t in tasks:
            if t not in self.tasks:
                self.go(t)
        return All(tasks)

    def call(self, func, duration=0.0):
        """Executa func(t) com t de 0 a 1 ao longo de `duration` (ou uma vez, se 0)."""
        if duration <= 0:
            func(1.0)
            return Wait(0)
        return Call(func, duration)

    def fade(self, alpha, duration=1.0):
        start = self.black.color.a

        def f(t):
            self.black.color = color.rgba(0, 0, 0, lerp(start, alpha, smooth(t)))
        return self.call(f, duration)

    def camera(self, position, look, duration=0.0):
        """Move a camera ate `position` olhando para `look` (ponto ou ator).
        Com duration=0 e um corte seco."""
        start_pos = Vec3(camera.world_position)
        start_look = Vec3(getattr(self, '_look', look if not isinstance(look, Entity) else look.position))
        position = Vec3(*position)

        def target():
            if isinstance(look, Entity):
                return look.world_position + Vec3(0, 1.4, 0)
            return Vec3(*look)

        def f(t):
            k = smooth(t) if duration > 0 else 1
            camera.world_position = lerp(start_pos, position, k)
            self._look = lerp(start_look, target(), k)
            aim_camera(self._look)
        self._track = None
        if getattr(self, '_camera_task', None):
            self._camera_task.cancelled = True      # um movimento novo substitui o anterior
        self._camera_task = self.call(f, duration)
        return self._camera_task

    def lens(self, fov):
        """Muda o campo de visao (lente mais aberta em lugares fechados)."""
        camera.fov = fov
        return Wait(0)

    def track(self, actor, offset=(0, 1.4, 0)):
        """A camera fica olhando para o ator (ate o proximo camera())."""
        self._track = (actor, Vec3(*offset))
        return Wait(0)

    def shake(self, duration=0.3, strength=0.15):
        base = Vec3(camera.world_position)

        def f(t):
            k = (1 - t) * strength
            camera.world_position = base + Vec3(math.sin(t * 90) * k, math.cos(t * 70) * k, 0)
        return self.call(f, duration)

    def walk(self, actor, target, speed=2.0, face=True):
        target = Vec3(*target)
        start = Vec3(actor.position)
        distance = max((target - start).length(), 1e-4)
        if face:
            d = target - start
            actor.rotation_y = math.degrees(math.atan2(d.x, d.z))

        def f(t):
            actor.position = lerp(start, target, t)
            actor.moving = t < 1
        return Call(f, distance / speed)

    def face(self, actor, point):
        p = Vec3(*point) if not isinstance(point, Entity) else point.position
        d = p - actor.position
        actor.rotation_y = math.degrees(math.atan2(d.x, d.z))
        return Wait(0)

    def say(self, speaker, text, auto=None):
        """Mostra uma fala. Espera Espaco/Enter/clique (ou o tempo de leitura, se auto)."""
        if self.dialogue:
            self.dialogue.closed = True
            destroy_tree(self.dialogue.root)
        self.dialogue = Dialogue(self, speaker, text, auto)
        return self.dialogue

    def title_card(self, text, sub='', duration=3.0):
        self.card.text, self.card_sub.text = text, sub

        def f(t):
            a = min(1.0, t * 5, (1 - t) * 4)
            self.card.alpha = a
            self.card_sub.alpha = a
        return self.call(f, duration)

    # -------------------------------------------------------------- loop
    def update(self):
        if self.ended:
            return
        dt = time.dt
        for task in list(self.tasks):
            if task.cancelled or task.step(dt):
                task.done = True
                self.tasks.remove(task)
        if getattr(self, '_track', None):
            actor, offset = self._track
            self._look = actor.world_position + offset
            aim_camera(self._look)
        while self.current is None or self.current.done:
            try:
                nxt = next(self._gen)
            except StopIteration:
                self.end(skipped=False)
                return
            if isinstance(nxt, (int, float)):
                nxt = Wait(nxt)
            self.current = nxt
            if nxt not in self.tasks:
                self.tasks.append(nxt)
            # tarefas instantaneas terminam ja no proximo laco
            if nxt.step(0):
                nxt.done = True
                self.tasks.remove(nxt)

    def input(self, key):
        if self.ended:
            return
        if key == 'escape':
            self.end(skipped=True)
        elif key in ('space', 'enter', 'left mouse down') and self.dialogue:
            self.dialogue.advance()

    def end(self, skipped):
        if self.ended:
            return
        self.ended = True
        if skipped:
            self._finish_state()
        for actor in self.actors:
            destroy_tree(actor)
        parent, pos, rot, fov = self.saved_camera
        camera.parent = parent
        camera.position = pos
        camera.rotation = rot
        camera.fov = fov
        destroy_tree(self)
        self.on_end(skipped)


class Dialogue(Task):
    """Caixa de dialogo com efeito de digitacao."""
    CHARS_PER_SECOND = 45

    def __init__(self, cs, speaker, text, auto):
        self.cs = cs
        self.full = text
        self.shown = 0.0
        self.finished_typing = False
        self.auto = auto if auto is not None else 2.2 + len(text) * 0.055   # nunca trava a cena
        self.after = 0.0
        self.closed = False
        self.root = Entity(parent=cs, y=-0.3, z=-2)
        Entity(parent=self.root, model='quad', scale=(1.3, 0.15), color=color.rgba(0.05, 0.05, 0.08, 0.85))
        Text(parent=self.root, text=speaker, position=(-0.62, 0.055), origin=(-0.5, 0.5), scale=1.25,
             color=color.rgb32(255, 210, 90))
        self.body = Text(parent=self.root, text=' ', position=(-0.62, 0.015), origin=(-0.5, 0.5), scale=1.15,
                         wordwrap=62)   # (texto vazio quebra o wordwrap do Ursina)
        self.hint = Text(parent=self.root, text='Espaço ▸', position=(0.62, -0.055), origin=(0.5, -0.5),
                         scale=0.8, color=color.rgba(1, 1, 1, 0))

    def advance(self):
        if not self.finished_typing:
            self.shown = len(self.full)      # completa o texto de uma vez
        else:
            self.closed = True

    def step(self, dt):
        if not self.finished_typing:
            self.shown = min(len(self.full), self.shown + dt * self.CHARS_PER_SECOND)
            self.body.text = self.full[:int(self.shown)] or ' '
            if self.shown >= len(self.full):
                self.finished_typing = True
                self.hint.color = color.rgba(1, 1, 1, 0.7)
        else:
            self.after += dt
            if self.after >= self.auto:
                self.closed = True
        if self.closed:
            if self.root:
                destroy_tree(self.root)
            if self.cs.dialogue is self:
                self.cs.dialogue = None
        return self.closed
