"""Teste automatico do jogo (sem abrir janela).

Monta o mundo numa janela invisivel, simula o heroi lutando na Campina dos Slimes,
visita as outras regioes, morre e renasce. Salva screenshots em tests/screenshots/.

Uso (de dentro da pasta rpg3d):
    python tests/test_jogo.py
"""
import math
import os
import sys
import time as pytime

GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(GAME_DIR, 'tests', 'screenshots')
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, GAME_DIR)
os.chdir(GAME_DIR)

from panda3d.core import Filename
from ursina import Entity, Ursina, Vec3, camera, color, distance_xz, mouse, window

app = Ursina(window_type='offscreen', size=(1280, 720), development_mode=False)
window.color = color.rgb32(170, 210, 255)
# janela invisivel nao suporta travar o mouse: troca por uma versao falsa
type(mouse).locked = property(lambda s: getattr(s, '_fake_lock', False),
                              lambda s, v: setattr(s, '_fake_lock', v))

failures = []


def check(condition, message):
    print(('  OK    ' if condition else '  FALHA ') + message)
    if not condition:
        failures.append(message)


def frames(n):
    for _ in range(n):
        app.step()


def shot(name):
    frames(2)
    app.win.saveScreenshot(Filename.fromOsSpecific(os.path.join(OUT, name)))


print('== Carregando o mundo')
t0 = pytime.perf_counter()
import tempfile  # noqa: E402
import save  # noqa: E402
save.use_directory(tempfile.mkdtemp(prefix='rpg3d_save_'))   # nunca mexe no seu save de verdade
from game import Game  # noqa: E402
game = Game(show_title=False)
build = pytime.perf_counter() - t0
p = game.player
check(build < 5, f'mundo carregou em {build:.2f}s')
check(len(game.enemies) > 0, f'{len(game.enemies)} inimigos criados')
check(p.equipped.name == 'Espada de Madeira', 'heroi comeca com a Espada de Madeira')
check(len(p.inventory.equippables()) == 1, 'e mais nenhuma arma ou ferramenta')
check(len(game.vendors) == 3, '3 lojas na vila')
check(len(game.world.nodes) > 100, f'{len(game.world.nodes)} recursos coletaveis no mapa')

frames(30)
t1 = pytime.perf_counter()
frames(120)
frame_ms = (pytime.perf_counter() - t1) / 120 * 1000
check(frame_ms < 33, f'tempo medio por frame: {frame_ms:.1f} ms')
shot('01_inicio.png')

print('== Combate na Campina dos Slimes')
p.position = Vec3(-22, 0, -16)
p.cam_pivot.rotation_y = 225
frames(60)
for i in range(900):
    app.step()
    alive = [e for e in game.enemies if not e.dead and distance_xz(e, p) < 12]
    if alive and not p.attacking:
        target = min(alive, key=lambda e: distance_xz(e, p))
        d = target.position - p.position
        p.cam_pivot.rotation_y = math.degrees(math.atan2(d.x, d.z))
        if distance_xz(target, p) < 2.5:
            p.start_attack()
        else:
            p.position += Vec3(d.x, 0, d.z).normalized() * 0.08
    if i == 200:
        shot('02_combate.png')
    if p.dead:
        break
frames(120)
print(f'  -> abates {p.kills}, nivel {p.level}, xp {p.xp}, vida {round(p.hp)}/{p.max_hp}, '
      f'moedas {p.coins}')
check(not any(isinstance(e, Entity) and type(e).__name__ != 'Coin' for e in game.pickups),
      'monstros so derrubam moedas (nenhuma pocao)')
check(p.kills > 0, 'derrotou inimigos')
check(p.level > 1 or p.xp > 0, 'ganhou XP')
check(p.coins > 0, 'coletou moedas')
shot('03_depois_do_combate.png')

print('== Visitando as outras regioes')
for name, pos, yaw, area in [('04_goblins.png', Vec3(40, 0, 17), 60, 'Acampamento Goblin'),
                             ('05_cemiterio.png', Vec3(-9, 0, 44), 0, 'Cemitério Esquecido')]:
    p.position = pos
    p.cam_pivot.rotation_y = yaw
    frames(90)
    shot(name)
    check(game.current_area == area, f'entrou em {area}')

print('== Morte e renascimento')
p.invulnerable = 0
p.take_damage(9999, p.position + Vec3(1, 0, 0))
frames(30)
check(p.dead, 'heroi morre com dano fatal')
shot('06_morte.png')
game.input('r')
frames(30)
check(not p.dead and p.hp == p.max_hp, 'renasce com vida cheia')
check(game.current_area == 'Vila de Carvalho', 'renasce na vila')

print('== Lojas')
from catalog import ITEMS  # noqa: E402
from world import SHOP_SPOTS, facing_center  # noqa: E402


def stand_in_front_of(kind):
    x, z = SHOP_SPOTS[kind]
    yaw = math.radians(facing_center(x, z))
    p.position = Vec3(x + math.sin(yaw) * 2.6, 0, z + math.cos(yaw) * 2.6)
    frames(5)


p.coins = 500
for kind in ('food', 'smith', 'witch'):
    stand_in_front_of(kind)
    vendor = game.nearest_vendor()
    check(vendor is not None and vendor.shop.kind == kind, f'perto da loja {kind}: aparece [F]')
    game.input('f')
    frames(3)
    check(game.menu is game.shop_menus[kind] and game.blocked, f'F abre o menu da loja {kind}')
    shot(f'08_loja_{kind}.png')
    menu = game.menu
    for item_id in menu.shop.stock:
        before = p.coins
        menu.buy(item_id)
        check(p.inventory.has(item_id) and p.coins == before - ITEMS[item_id].price,
              f'comprou {ITEMS[item_id].name} por {ITEMS[item_id].price}')
    game.input('escape')
    frames(3)
    check(game.menu is None and not game.blocked, 'Esc fecha a loja')

before = p.coins
game.shop_menus['smith'].buy('machado')
check(p.coins == before and p.inventory.count('machado') == 1, 'nao compra ferramenta repetida')
p.coins = 3
game.shop_menus['witch'].buy('pocao_vida')
check(p.coins == 3, 'nao compra sem moedas suficientes')

print('== Comida e fome')
p.hunger = 40
p.hp = 50
hp0 = p.hp
p.consume('pera')
check(p.hunger == 70 and p.hp == hp0 + 14, f'Pera: +30 fome e +14 vida (fome {p.hunger}, vida {p.hp})')
p.hunger = 50
frames(1)
h0 = p.hunger
game.player.update()
check(p.hunger < h0, 'fome diminui com o tempo')
p.hunger = 0
p.hp = 60
p._starve_tick = 0.99
p.update()
check(p.hp < 60, 'com fome zerada perde vida')
p.hunger = 100
p.hp = 50
p.drink_potion()
check(p.hp == 50 + int(p.max_hp * 0.4), 'Pocao de Vida cura 40%')
p.hp = p.max_hp

print('== Ferramentas e coleta')
def face(node):
    p.position = Vec3(node.x, 0, node.z) - Vec3(node.radius + 1.0, 0, 0)
    p.rotation_y = 90
    p.cam_pivot.rotation_y = 90


def swing():
    p.start_attack()
    for _ in range(120):
        app.step()
        if not p.attacking:
            break


from models import set_dormant  # noqa: E402
game._stream_timer = 1e9     # congela todos os monstros para testar a coleta em paz
for e in game.enemies:
    set_dormant(e, True)
game.awake_enemies = []

for kind, tool, material in (('tree', 'machado', 'madeira'), ('rock', 'picareta', 'pedra'),
                             ('plant', 'foice', 'ervas')):
    node = next(n for n in game.world.nodes if n.kind == kind and not n.depleted)
    face(node)
    p.equip('espada_madeira')
    before = p.inventory.count(material)
    swing()
    check(p.inventory.count(material) == before, f'{node.label} nao e coletada com a espada')
    p.equip(tool)
    for _ in range(node.max_hits):
        face(node)
        swing()
    check(p.inventory.count(material) > before, f'{ITEMS[tool].name} coleta {material} '
                                               f'(+{p.inventory.count(material) - before})')
    check(node.depleted, f'{node.label} some depois de {node.max_hits} golpe(s)')
    if node.obstacle:
        check(not node.obstacle.active, f'{node.label} cortada nao bloqueia mais a passagem')
shot('09_coleta.png')

print('== Fabricar armas de pedra')
p.inventory.add('madeira', 20 - p.inventory.count('madeira'))
p.inventory.add('pedra', 30 - p.inventory.count('pedra'))
smith = game.shop_menus['smith']
smith.craft(next(r for r in __import__('catalog').RECIPES if r.result == 'espada_pedra'))
check(p.inventory.has('espada_pedra') and p.equipped.id == 'espada_pedra', 'fabricou e equipou Espada de Pedra')
check(ITEMS['espada_pedra'].damage > ITEMS['espada_madeira'].damage, 'Espada de Pedra e mais forte que a de madeira')
smith.craft(next(r for r in __import__('catalog').RECIPES if r.result == 'martelo_pedra'))
check(p.inventory.has('martelo_pedra'), 'fabricou Martelo de Pedra')
check(p.inventory.count('madeira') == 10 and p.inventory.count('pedra') == 8, 'gastou os materiais certos')

print('== Inventario')
game.input('tab')
frames(3)
check(game.menu is game.inventory_menu, 'Tab abre o inventario')
shot('10_inventario.png')
game.input('tab')
check(game.menu is None, 'Tab fecha o inventario')
p.input('1')
check(p.equipped.id == p.inventory.equippables()[0].id, 'tecla 1 equipa o primeiro item')

game._stream_timer = 0      # volta o streaming ao normal
frames(30)
shot('11_hud.png')

print('== Desempenho: nevoa, pedacos do mapa e mobs dormentes')
from settings import ACTIVE_DISTANCE, SLEEP_DISTANCE, VIEW_DISTANCE  # noqa: E402
from items import Coin  # noqa: E402
check(camera.clip_plane_far == VIEW_DISTANCE, f'nada e desenhado alem de {VIEW_DISTANCE} m')
check(len(game.world.static_chunks) > 20, f'cenario dividido em {len(game.world.static_chunks)} pedacos')
p.position = Vec3(45, 0, -55)        # canto sudeste: cemiterio e campina ficam bem longe
game._update_streaming(force=True)
far = [e for e in game.enemies if distance_xz(e, p) > SLEEP_DISTANCE]
near = [e for e in game.enemies if distance_xz(e, p) < ACTIVE_DISTANCE]
check(far and all(e.dormant for e in far), f'{len(far)} mobs longe estao dormentes')
check(all(not e.dormant for e in near), f'{len(near)} mobs perto estao ativos')
mob = max(far, key=lambda e: distance_xz(e, p))     # o mais distante (bem fora da faixa de folga)
mob_pos, mob_hp = Vec3(mob.position), mob.hp
frames(60)
check((mob.position - mob_pos).length() < 0.01, 'mob dormente fica parado (nao gasta processamento)')
coin = Coin(game, mob.position + Vec3(3, 0, 0), 7)
frames(40)                                  # deixa a moeda cair no chao
coin_pos = Vec3(coin.position)
game._update_streaming(force=True)
frames(20)
check(coin.dormant and coin in game.pickups, 'moeda longe fica dormente (nao some)')
p.position = mob.position + (p.position - mob.position).normalized() * 15   # chega perto
game._update_streaming(force=True)
check(not mob.dormant and not coin.dormant, 'chegando perto, mobs e moedas acordam')
check((coin.position - coin_pos).length() < 0.01, 'moeda continua exatamente onde caiu')
check((mob.position - mob_pos).length() < 0.01 and mob.hp == mob_hp, 'mob acorda na mesma posicao e com a mesma vida')
coin.remove()
p.position = Vec3(-9, 0, -7.2)
game._update_streaming(force=True)

print('== Camera com o mouse')
from settings import MOUSE_SENSITIVITY  # noqa: E402
mouse.locked = True
p.mouse_grace = 0
for label, speed in (('lento', 0.01), ('rapido', 0.4), ('muito rapido', 0.8)):
    before = p.cam_pivot.rotation_y
    mouse.velocity = Vec3(speed, 0, 0)
    p._update_camera(1 / 60)
    turned = p.cam_pivot.rotation_y - before
    check(abs(turned - speed * MOUSE_SENSITIVITY) < 0.01, f'movimento {label} gira a camera ({turned:.1f} graus)')
mouse.velocity = Vec3(0, 0, 0)

print('== Musica')
import wave  # noqa: E402
import music  # noqa: E402
check(music.MUSIC_FILE.exists(), 'arquivo da musica foi gerado')
with wave.open(str(music.MUSIC_FILE)) as wf:
    seconds = wf.getnframes() / wf.getframerate()
check(abs(seconds - 48) < 0.01, f'musica tem {seconds:.1f} s (24 compassos a 120 BPM)')
mp = game.music
check(mp.audio is not None and mp.audio.loop, 'musica tocando em loop')
frames(200)
check(abs(mp.audio.volume - mp.volume) < 0.05, f'musica entra suave ate o volume {mp.volume}')
game.input('m')
frames(1)
t_end = pytime.perf_counter() + 1.0
while pytime.perf_counter() < t_end:
    app.step()
check(not mp.enabled and mp.audio.volume < 0.01, 'tecla M desliga a musica')
game.input('m')
frames(1)
t_end = pytime.perf_counter() + 1.0
while pytime.perf_counter() < t_end:
    app.step()
check(mp.enabled and abs(mp.audio.volume - mp.volume) < 0.05, 'tecla M liga de novo')

print('== Salvar e carregar')
from items import Coin  # noqa: E402
p.position = Vec3(12, 0, -20)
p.hunger, p.coins, p.kills = 55.5, 321, 17
p.inventory.add('pocao_vida', 2)
p.equip('espada_pedra')
rock = next(n for n in game.world.nodes if n.kind == 'rock' and not n.depleted)
rock.hits_left = 2                                        # rocha meio quebrada
tree = next(n for n in game.world.nodes if n.kind == 'tree' and not n.depleted and n is not rock)
for _ in range(tree.max_hits):
    tree.hit()                                            # arvore cortada
ground_coin = Coin(game, Vec3(22, 0, -20), 9)           # longe do ima de moedas do heroi
frames(40)
expected = dict(level=p.level, xp=p.xp, coins=p.coins, kills=p.kills, hunger=p.hunger,
                inventory=dict(p.inventory.counts), equipped=p.equipped.id, pos=Vec3(p.position))
coin_pos = Vec3(ground_coin.position)
check(game.save_game(notify=False) and save.SAVE_FILE.exists(), 'jogo salvo em arquivo')
game.save_game(notify=False)                             # 2o save -> cria o backup
check(save.BACKUP_FILE.exists(), 'save anterior fica como backup')

# baguncar tudo, como se fosse outra sessao
p.coins, p.kills, p.hunger = 0, 0, 100
p.inventory.counts = {'espada_madeira': 1}
p.equip('espada_madeira', silent=True)
p.position = Vec3(0, 0, 5)
rock.hits_left = rock.max_hits
tree.depleted, tree.visible, tree.hits_left = False, True, tree.max_hits
tree.obstacle.active = True
ground_coin.remove()

game._show_title()
frames(3)
check(game.title is not None and game.blocked, 'tela inicial aparece e pausa o jogo')
shot('12_tela_inicial.png')
game.continue_game()
frames(5)
check(game.title is None and not game.blocked, 'Continuar fecha a tela inicial')
check(p.coins == expected['coins'] and p.kills == expected['kills'] and p.level == expected['level']
      and p.xp == expected['xp'], 'nivel, XP, moedas e abates restaurados')
check(abs(p.hunger - expected['hunger']) < 0.5, 'fome restaurada')   # ela cai um pouco a cada frame
check(p.inventory.counts == expected['inventory'], 'inventario restaurado')
check(p.equipped.id == expected['equipped'], f'item equipado restaurado ({p.equipped.name})')
check((p.position - expected['pos']).length() < 0.6, 'posicao restaurada')
check(rock.hits_left == 2 and not rock.depleted, 'rocha continua meio quebrada')
check(tree.depleted and not tree.obstacle.active, 'arvore continua cortada')
check(any(isinstance(c, Coin) and c.value == 9 and (c.position - coin_pos).length() < 0.01
          for c in game.pickups), 'moeda no chao volta no mesmo lugar')

save.SAVE_FILE.write_text('{ isso nao e um save', encoding='utf-8')
try:
    data = save.read_save()
    check(data['player']['coins'] == expected['coins'], 'save corrompido -> usa o backup')
except save.SaveError:
    check(False, 'save corrompido -> usa o backup')
game._on_window_close()                                  # fechar no X
check(save.read_save()['player']['coins'] == p.coins, 'fechar a janela salva o jogo')

print('== Pausa')
game.toggle_pause()
frames(5)
check(game.paused, 'jogo pausa')
t_end = pytime.perf_counter() + 1.0          # o fade dura 0,6 s
while pytime.perf_counter() < t_end:
    app.step()
check(abs(game.music.audio.volume - game.music.quiet_volume) < 0.05, 'musica abaixa na pausa')
shot('07_pausa.png')
game.toggle_pause()
check(not game.paused, 'jogo despausa')

print()
print(f'Screenshots em: {OUT}')
if failures:
    print(f'RESULTADO: {len(failures)} falha(s)')
    sys.exit(1)
print('RESULTADO: tudo certo!')
