"""Junta tudo: mundo, jogador, inimigos, lojas, menus, pausa e game over."""
import math
import random

from panda3d.core import PNMImage, Texture as PandaTexture
from ursina import (AmbientLight, DirectionalLight, Entity, Sky, Texture, Vec3, application, camera, color,
                    lerp, mouse, scene, time, window)
from ursina.shaders.unlit_shader import unlit_shader

from catalog import ITEMS, TOOL, TOOL_ITEM
from enemies import Goblin, Skeleton, Slime
from menus import InventoryMenu, ShopMenu, TitleScreen
from models import Glow, destroy_tree, set_dormant, setup_shared_shader_inputs, update_shared_shader_inputs
import save
import story
from music import MusicPlayer
from player import Player
from settings import (ACTIVE_DISTANCE, FOG_COLOR, MUSIC_PAUSED_VOLUME, MUSIC_VOLUME, SHADOW_MAP_SIZE, SKY_TOP_COLOR, SLEEP_DISTANCE,
                      VIEW_DISTANCE, VILLAGE_RADIUS)
from shops import INTERACT_DISTANCE, SHOPS, ShopNPC
from ui import HUD, Overlay
from world import GOBLIN_CAMP, GRAVEYARD, SLIME_MEADOW, World

AUTOSAVE_INTERVAL = 60   # segundos de jogo entre salvamentos automaticos
VILLAGE_REGEN = 0.05    # fracao da vida maxima por segundo dentro da vila (se nao estiver faminto)
STREAM_INTERVAL = 0.25   # de quanto em quanto tempo checa quem dorme/acorda

# iluminacao do dia e da noite
DAY_SUN, NIGHT_SUN = color.rgb(0.95, 0.9, 0.82), color.rgb(0.22, 0.28, 0.48)
DAY_AMBIENT, NIGHT_AMBIENT = color.rgb(0.5, 0.52, 0.6), color.rgb(0.13, 0.15, 0.27)
NIGHT_FOG = color.rgb32(16, 22, 42)
NIGHT_SKY_TINT = color.rgb(0.1, 0.13, 0.27)


def _sky_gradient():
    """Textura do ceu: azul no alto, clareando ate a cor da nevoa no horizonte."""
    height = 128
    img = PNMImage(4, height)
    for y in range(height):
        t = min(1.0, y / (height / 2))          # 0 no topo da imagem, 1 no horizonte (meio)
        c = lerp(SKY_TOP_COLOR, FOG_COLOR, t ** 1.6)
        for x in range(4):
            img.setXel(x, y, c[0], c[1], c[2])
    tex = PandaTexture('sky_gradient')
    tex.load(img)
    return Texture(tex)


class Zone:
    """Area onde um tipo de inimigo nasce e renasce."""

    def __init__(self, name, center, radius, enemy_cls, max_count, respawn_delay, subtitle=''):
        self.name = name
        self.subtitle = subtitle
        self.center = Vec3(center[0], 0, center[1])
        self.radius = radius
        self.enemy_cls = enemy_cls
        self.max_count = max_count
        self.respawn_delay = respawn_delay
        self.timer = 0.0
        self.alive = 0


class Game(Entity):
    def __init__(self, show_title=True):
        super().__init__(ignore_paused=True)
        self.paused = False      # tela de pausa (Esc)
        self.menu = None         # menu aberto (loja / inventario)
        self.cutscene = None     # cena em andamento
        self.objective = ''      # objetivo atual da historia (aparece no HUD)
        self.intro_done = False
        self.enemies = []
        self.awake_enemies = []  # so os mobs perto do jogador (os outros estao dormentes)
        self.pickups = []
        self._stream_timer = 0.0

        self._setup_lighting()
        self.world = World()
        self.hud = HUD()
        self.player = Player(self)
        self.hud.refresh(self.player)

        self.zones = [
            Zone('Campina dos Slimes', SLIME_MEADOW, 15, Slime, 9, 5, 'Perigo: baixo'),
            Zone('Bosque do Sul', (24, -34), 8, Slime, 4, 8, 'Perigo: baixo'),
            Zone('Acampamento Goblin', GOBLIN_CAMP, 11, Goblin, 6, 9, 'Perigo: médio'),
            Zone('Cemitério Esquecido', GRAVEYARD, 13, Skeleton, 5, 14, 'Perigo: alto'),
        ]
        for zone in self.zones:
            for _ in range(zone.max_count):
                self._spawn(zone, check_player=False)
        self._update_streaming(force=True)
        self.current_area = None

        # lojas
        self.vendors = [ShopNPC(self, shop) for shop in SHOPS.values()]
        self.shop_menus = {kind: ShopMenu(self, shop) for kind, shop in SHOPS.items()}
        self.inventory_menu = InventoryMenu(self)

        self.pause_screen = Overlay('PAUSADO', '')
        self.death_screen = Overlay('VOCÊ MORREU', 'Pressione R para renascer na vila', color.rgb32(230, 60, 60))

        self.music = MusicPlayer(MUSIC_VOLUME, MUSIC_PAUSED_VOLUME)

        # salvar / carregar
        self.play_time = 0.0
        self._autosave_timer = AUTOSAVE_INTERVAL
        self.started = False     # False enquanto a tela inicial esta aberta
        self.title = None
        application.base.exitFunc = self._on_window_close   # fechar no X tambem salva
        if show_title:
            self._show_title()
        else:
            self._begin()

    @property
    def blocked(self):
        """True quando o jogador nao pode agir (tela inicial, cena, pausa ou menu aberto)."""
        return (self.title is not None or self.cutscene is not None or self.paused
                or self.menu is not None)

    def set_objective(self, text):
        self.objective = text
        self.hud.set_objective(text)

    # ===================================================== salvar / carregar
    def _show_title(self):
        summary, problem = None, None
        if save.save_exists():
            try:
                summary = save.summary(save.read_save())
            except save.SaveError as error:
                problem = str(error)
        self.title = TitleScreen(self, summary, problem)
        self.hud.enabled = False
        application.paused = True
        mouse.locked = False

    def _close_title(self):
        if self.title:
            destroy_tree(self.title)
            self.title = None
        self.hud.enabled = True
        application.paused = False

    def _begin(self):
        self.started = True
        self.lock_mouse(True)

    def start_new_game(self, intro=True):
        self._close_title()
        if intro:
            mouse.locked = False
            story.play_intro(self, on_done=self._after_intro)    # cena de abertura (Esc pula)
        else:
            self._after_intro()

    def _after_intro(self):
        self.intro_done = True
        self.set_objective(story.INTRO_OBJECTIVE)
        self._update_streaming(force=True)
        self._begin()
        self.hud.notify('Dica: compre equipamentos nas lojas da praça (F) antes de partir.', duration=5)
        self.save_game(notify=False)      # o novo jogo substitui o save antigo

    def continue_game(self):
        try:
            data = save.read_save()
            self._close_title()
            save.apply(self, data)
        except (save.SaveError, KeyError, TypeError, ValueError) as error:
            self.hud.notify(f'Não foi possível carregar o save ({error}). Começando um novo jogo.', duration=4)
            self.start_new_game()
            return
        self._update_streaming(force=True)
        self._begin()
        self.hud.show_message('Bem-vindo de volta!', save.summary(data), duration=3)

    def save_game(self, notify=True):
        if not self.started:
            return False
        try:
            save.write_save(save.serialize(self))
        except OSError as error:
            self.hud.notify(f'Erro ao salvar: {error}', duration=3)
            return False
        self._autosave_timer = AUTOSAVE_INTERVAL
        if notify:
            self.hud.notify('Jogo salvo', duration=1.2)
        return True

    def quit_game(self):
        self.save_game(notify=False)
        application.quit()

    def _on_window_close(self):
        self.save_game(notify=False)

    def _update_autosave(self):
        self.play_time += time.dt
        self._autosave_timer -= time.dt
        if self._autosave_timer <= 0 and not self.player.dead:
            self.save_game()

    # ============================================================ luz/ceu
    def _setup_lighting(self):
        # nevoa + limite de visao: o que fica alem de VIEW_DISTANCE nem e desenhado
        setup_shared_shader_inputs()
        camera.clip_plane_far = VIEW_DISTANCE
        window.color = FOG_COLOR
        self.sky = Sky(texture=_sky_gradient(), color=color.white)
        self.sky.setDepthWrite(False)     # o ceu nunca tampa o cenario
        self.sun = DirectionalLight(shadow_map_resolution=(SHADOW_MAP_SIZE, SHADOW_MAP_SIZE))
        self.sun.look_at(Vec3(0.6, -1, 0.9))
        self.ambient = AmbientLight()
        # lua: so aparece a noite (fica "pendurada" no ceu, que acompanha a camera)
        self.moon = Entity(parent=self.sky, model='circle', position=Vec3(0.25, 0.3, 0.32), billboard=True,
                           scale=0.035, shader=unlit_shader, color=color.rgba(1, 1, 0.92, 0))
        self.moon.setBin('background', 1)
        self.moon.setDepthWrite(False)
        # caixa invisivel que segue o jogador: define a area que recebe sombras
        self.shadow_box = Entity(model='cube', scale=(55, 25, 55), visible=False)
        self._shadow_timer = 0
        self.daylight = 1.0        # 0 = meia-noite, 1 = dia claro
        self._dawn_speed = 0.0     # >0 enquanto esta amanhecendo
        self.set_daylight(1.0)

    def set_daylight(self, d):
        """Ajusta toda a iluminacao entre noite (0) e dia (1)."""
        self.daylight = d = max(0.0, min(1.0, d))
        self.sun.color = lerp(NIGHT_SUN, DAY_SUN, d)
        self.ambient.color = lerp(NIGHT_AMBIENT, DAY_AMBIENT, d)
        fog = lerp(NIGHT_FOG, FOG_COLOR, d)
        scene.set_shader_input('fog_color', fog)
        window.color = fog
        self.sky.color = lerp(NIGHT_SKY_TINT, color.white, d)
        self.moon.color = color.rgba(1, 1, 0.92, max(0.0, 1 - d * 1.6))
        Glow.night = 1 - d

    def start_dawn(self, duration):
        """O dia nasce aos poucos, de onde esta ate o dia claro."""
        self._dawn_speed = (1 - self.daylight) / max(duration, 0.1)

    def _update_dawn(self):
        if self._dawn_speed > 0:
            self.set_daylight(self.daylight + self._dawn_speed * time.dt)
            if self.daylight >= 1:
                self._dawn_speed = 0

    def focus_shadows(self, point):
        """Centra a area com sombras num ponto (o jogador, ou o foco de uma cutscene)."""
        self.shadow_box.position = Vec3(point[0], 0, point[2])
        self.sun.update_bounds(self.shadow_box)

    def _update_shadows(self):
        self._shadow_timer -= time.dt
        if self._shadow_timer <= 0:
            self._shadow_timer = 0.2
            self.focus_shadows(self.player.position)

    # ============================================================= spawner
    def _spawn(self, zone, check_player=True):
        for _ in range(30):
            a = random.uniform(0, math.tau)
            r = math.sqrt(random.random()) * zone.radius
            pos = zone.center + Vec3(math.cos(a) * r, 0, math.sin(a) * r)
            if not self.world.is_free(pos.x, pos.z, 1.0):
                continue
            if math.hypot(pos.x, pos.z) < VILLAGE_RADIUS + 3:
                continue
            if check_player and (pos - self.player.position).length() < 12:
                continue
            enemy = zone.enemy_cls(self, pos, zone)
            enemy.rotation_y = random.uniform(0, 360)
            self.enemies.append(enemy)
            self._stream(enemy)
            zone.alive += 1
            return enemy
        return None

    # ===================================================== dormencia (streaming)
    def _stream(self, entity):
        """Acorda quem esta perto do jogador e congela quem esta longe.

        Dormentes nao sao desenhados nem atualizados, mas continuam existindo com a
        mesma posicao, vida e estado (moedas no chao continuam exatamente onde cairam).
        """
        d = math.hypot(entity.x - self.player.x, entity.z - self.player.z)
        if getattr(entity, 'dormant', False):
            if d < ACTIVE_DISTANCE:
                set_dormant(entity, False)
        elif d > SLEEP_DISTANCE:
            set_dormant(entity, True)

    def _update_streaming(self, force=False):
        self._stream_timer -= time.dt
        if self._stream_timer > 0 and not force:
            return
        self._stream_timer = STREAM_INTERVAL
        for enemy in self.enemies:
            self._stream(enemy)
        for pickup in self.pickups:
            self._stream(pickup)
        self.awake_enemies = [e for e in self.enemies if not getattr(e, 'dormant', False)]

    def _update_spawner(self):
        for zone in self.zones:
            if zone.alive >= zone.max_count:
                zone.timer = zone.respawn_delay
                continue
            zone.timer -= time.dt
            if zone.timer <= 0:
                zone.timer = zone.respawn_delay
                self._spawn(zone)

    def on_enemy_killed(self, enemy):
        if enemy in self.enemies:
            self.enemies.remove(enemy)
        if enemy in self.awake_enemies:
            self.awake_enemies.remove(enemy)
        if enemy.zone:
            enemy.zone.alive -= 1
        self.player.kills += 1
        self.player.gain_xp(enemy.XP)

    # ============================================================== areas
    def _area_at(self, pos):
        if math.hypot(pos.x, pos.z) < VILLAGE_RADIUS + 1:
            return 'Vila de Carvalho', 'Zona segura'
        for zone in self.zones:
            if (pos - zone.center).length() < zone.radius + 5:
                return zone.name, zone.subtitle
        return 'Floresta', ''

    def _update_area(self):
        name, subtitle = self._area_at(self.player.position)
        if name != self.current_area:
            if self.current_area is not None and name != 'Floresta':
                self.hud.show_message(name, subtitle, duration=2)
            self.current_area = name
            self.hud.zone_text.text = name

    # ========================================================= interacao
    def nearest_vendor(self):
        best = min(self.vendors, key=lambda v: v.distance_to_player())
        return best if best.distance_to_player() < INTERACT_DISTANCE else None

    def _update_prompt(self):
        p = self.player
        if p.dead or self.blocked:
            self.hud.set_prompt('')
            return
        vendor = self.nearest_vendor()
        if vendor:
            self.hud.set_prompt(f'[F] {vendor.shop.title}')
            return
        node = self.world.nearest_node(p.position, 1.6)
        if node:
            tool_id = TOOL_ITEM[node.tool]
            tool = ITEMS[tool_id].name
            if p.equipped.kind == TOOL and p.equipped.tool == node.tool:
                self.hud.set_prompt(f'{node.label}: clique para coletar')
            elif p.inventory.has(tool_id):
                slot = [e.id for e in p.inventory.equippables()].index(tool_id) + 1
                self.hud.set_prompt(f'{node.label}: equipe a {tool} (tecla {slot})')
            else:
                self.hud.set_prompt(f'{node.label}: precisa de {tool} (Ferraria)')
            return
        self.hud.set_prompt('')

    # ============================================================== menus
    def open_menu(self, menu):
        if self.menu:
            self.menu.close()
        self.menu = menu
        menu.open()
        application.paused = True
        self.lock_mouse(False)
        self.hud.set_prompt('')

    def close_menu(self):
        if not self.menu:
            return
        self.menu.close()
        self.menu = None
        application.paused = False
        self.lock_mouse(True)
        self.hud.refresh(self.player)

    # ========================================================= game loop
    def update(self):
        update_shared_shader_inputs()
        if self.blocked:
            return
        self.world.update(self.player.position)
        self._update_streaming()
        self._update_shadows()
        self._update_dawn()
        self._update_spawner()
        self._update_area()
        self._update_prompt()
        self._update_autosave()
        p = self.player
        # cura lenta dentro da vila (so se nao estiver morrendo de fome)
        if not p.dead and self.current_area == 'Vila de Carvalho' and p.hp < p.max_hp and p.hunger > 0:
            p.hp = min(p.max_hp, p.hp + p.max_hp * VILLAGE_REGEN * time.dt)
        # a barra de fome e a vida mudam aos poucos: atualiza o HUD algumas vezes por segundo
        self._hud_tick = getattr(self, '_hud_tick', 0) + time.dt
        if self._hud_tick > 0.25:
            self._hud_tick = 0
            self.hud.refresh(p)

    def input(self, key):
        p = self.player
        if self.title or self.cutscene:     # tela inicial e cenas cuidam das proprias teclas
            if key == 'm':
                self.music.toggle()
            return
        if key == 'escape':
            if self.menu:
                self.close_menu()
            elif not p.dead:
                self.toggle_pause()
        elif key == 'q' and self.paused:
            self.quit_game()
        elif key == 'g' and self.paused:
            if self.save_game(notify=False):
                self.pause_screen.subtitle.text = self._pause_text('Jogo salvo!')
        elif key == 'm':
            on = self.music.toggle()
            self.hud.notify('Música ligada' if on else 'Música desligada', duration=1.2)
        elif key == 'r' and p.dead:
            self.respawn_player()
        elif key == 'tab' and not self.paused and not p.dead:
            if self.menu is self.inventory_menu:
                self.close_menu()
            elif self.menu is None:
                self.open_menu(self.inventory_menu)
        elif key == 'f' and not self.paused and not p.dead:
            if self.menu in self.shop_menus.values():
                self.close_menu()
            elif self.menu is None:
                vendor = self.nearest_vendor()
                if vendor:
                    self.open_menu(self.shop_menus[vendor.shop.kind])
        elif key == 'left mouse down' and not self.blocked and not mouse.locked:
            self.lock_mouse(True)

    def lock_mouse(self, value):
        mouse.locked = value
        if value:
            self.player.mouse_grace = 0.25

    def _pause_text(self, status=''):
        p = self.player
        return (f'Nível {p.level}   |   Monstros derrotados: {p.kills}   |   Moedas: {p.coins}   |   '
                f'Tempo de jogo: {save.format_play_time(self.play_time)}\n\n'
                f'Esc continuar     G salvar     M música     Q salvar e sair'
                + (f'\n\n{status}' if status else ''))

    def toggle_pause(self):
        self.paused = not self.paused
        application.paused = self.paused
        self.lock_mouse(not self.paused)
        self.music.set_quiet(self.paused)
        if self.paused:
            self.pause_screen.show(self._pause_text())
        else:
            self.pause_screen.hide()

    # =========================================================== morte
    def on_player_died(self):
        lost = self.player.coins // 4
        self.player.coins -= lost
        self.lock_mouse(False)
        self.music.set_quiet(True)
        self.death_screen.show(f'Você perdeu {lost} moedas.\n\nPressione R para renascer na vila')

    def respawn_player(self):
        self.death_screen.hide()
        self.music.set_quiet(False)
        self.player.respawn()
        self.lock_mouse(True)
        # inimigos que estavam perseguindo voltam para casa
        for enemy in self.enemies:
            if enemy.state in ('chase', 'windup', 'recover', 'stagger'):
                enemy.set_state('return')
        self.hud.show_message('Você renasceu', 'Cuidado lá fora!', duration=2)
