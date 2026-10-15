"""Salvar e carregar o progresso (arquivo JSON em saves/).

O que e salvo:
  - heroi: nivel, XP, vida, fome, moedas, monstros derrotados, posicao e direcao
  - inventario completo e o item equipado
  - mundo: arvores/rochas/plantas ja coletadas (e quanto falta para renascerem)
    e as moedas que estao no chao (com a mesma posicao)
  - tempo de jogo e se a musica esta ligada
Os monstros NAO sao salvos: eles renascem nas suas areas ao carregar.

Seguranca: o arquivo e gravado primeiro num .tmp e so depois substitui o save
(um travamento no meio da gravacao nao corrompe o save), e a versao anterior fica
como .bak. Se o save estiver corrompido, o jogo tenta o .bak.
"""
import json
import os
import time
from pathlib import Path

from catalog import ITEMS
from settings import MAX_HUNGER, PLAYER_SPAWN, PLAYER_SPAWN_YAW, WORLD_SEED

SAVE_VERSION = 1
SAVE_DIR = Path(__file__).resolve().parent / 'saves'
SAVE_FILE = SAVE_DIR / 'save.json'
BACKUP_FILE = SAVE_DIR / 'save.json.bak'


class SaveError(Exception):
    pass


def use_directory(path):
    """Muda a pasta dos saves (os testes usam uma pasta temporaria para nao tocar no seu save)."""
    global SAVE_DIR, SAVE_FILE, BACKUP_FILE
    SAVE_DIR = Path(path)
    SAVE_FILE = SAVE_DIR / 'save.json'
    BACKUP_FILE = SAVE_DIR / 'save.json.bak'


# ------------------------------------------------------------ arquivo
def save_exists():
    return SAVE_FILE.exists() or BACKUP_FILE.exists()


def write_save(data):
    SAVE_DIR.mkdir(exist_ok=True)
    tmp = SAVE_FILE.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    if SAVE_FILE.exists():
        os.replace(SAVE_FILE, BACKUP_FILE)
    os.replace(tmp, SAVE_FILE)


def _read(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get('version') != SAVE_VERSION or 'player' not in data:
        raise SaveError('formato de save desconhecido')
    return data


def read_save():
    """Le o save (ou o backup, se o principal estiver estragado)."""
    errors = []
    for path in (SAVE_FILE, BACKUP_FILE):
        if path.exists():
            try:
                return _read(path)
            except (OSError, ValueError, SaveError) as error:
                errors.append(f'{path.name}: {error}')
    raise SaveError('; '.join(errors) or 'nenhum save encontrado')


def delete_save():
    for path in (SAVE_FILE, BACKUP_FILE):
        if path.exists():
            path.unlink()


def format_play_time(seconds):
    minutes = int(seconds // 60)
    return f'{minutes // 60}h{minutes % 60:02d}' if minutes >= 60 else f'{minutes} min'


def summary(data):
    """Texto curto para a tela inicial."""
    p = data['player']
    saved = time.strftime('%d/%m/%Y %H:%M', time.localtime(data.get('saved_at', 0)))
    return (f'Nível {p["level"]}   ·   {p["coins"]} moedas   ·   '
            f'{format_play_time(data.get("play_time", 0))} de jogo   ·   salvo em {saved}')


# ------------------------------------------------------- jogo -> dados
def serialize(game):
    p = game.player
    if p.dead:   # salvar morto = salvar ja renascido na vila
        position, yaw, hp = list(PLAYER_SPAWN), PLAYER_SPAWN_YAW, p.max_hp
    else:
        position, yaw, hp = [p.x, 0.0, p.z], p.rotation_y, p.hp
    world = game.world
    return {
        'version': SAVE_VERSION,
        'saved_at': time.time(),
        'play_time': game.play_time,
        'music_on': game.music.enabled,
        'story': {'intro_done': game.intro_done, 'objective': game.objective},
        'player': {
            'level': p.level, 'xp': p.xp, 'max_hp': p.max_hp, 'hp': round(hp, 2),
            'hunger': round(p.hunger, 2), 'coins': p.coins, 'kills': p.kills,
            'position': [round(v, 3) for v in position], 'yaw': round(yaw, 2),
            'camera_yaw': round(p.cam_pivot.rotation_y, 2),
            'inventory': dict(p.inventory.counts), 'equipped': p.equipped.id,
        },
        'world': {
            'seed': WORLD_SEED,
            'node_count': len(world.nodes),
            # so os recursos que mudaram: [indice, golpes restantes, segundos para renascer]
            'nodes': [[i, n.hits_left, round(n.regrow_timer, 1) if n.depleted else 0]
                      for i, n in enumerate(world.nodes) if n.depleted or n.hits_left < n.max_hits],
            'coins': [[round(c.x, 3), round(c.y, 3), round(c.z, 3), c.value, round(c.age, 1)]
                      for c in game.pickups if c.landed],
        },
    }


# ------------------------------------------------------- dados -> jogo
def apply(game, data):
    """Restaura um save num jogo recem-criado."""
    from ursina import Vec3
    from items import Coin

    p = game.player
    d = data['player']
    p.level = max(1, int(d['level']))
    from settings import xp_for_level
    p.xp_next = xp_for_level(p.level)
    p.xp = max(0, int(d['xp']))
    p.max_hp = int(d['max_hp'])
    p.hp = min(p.max_hp, max(1.0, float(d['hp'])))
    p.hunger = min(MAX_HUNGER, max(0.0, float(d['hunger'])))
    p.coins = max(0, int(d['coins']))
    p.kills = max(0, int(d['kills']))

    # inventario: ignora itens que nao existem mais no catalogo
    p.inventory.counts = {}
    for item_id, count in d['inventory'].items():
        if item_id in ITEMS and int(count) > 0:
            p.inventory.counts[item_id] = min(int(count), ITEMS[item_id].max_stack)
    if not p.inventory.equippables():
        p.inventory.counts['espada_madeira'] = 1
    equipped = d.get('equipped')
    p.equipped = ITEMS['espada_madeira']   # forca reconstruir o modelo na mao
    p.equip(equipped if p.inventory.has(equipped or '') else p.inventory.equippables()[0].id, silent=True)

    x, _, z = d['position']
    p.position = game.world.resolve_collision(Vec3(x, 0, z), p.RADIUS)
    p.rotation_y = d.get('yaw', PLAYER_SPAWN_YAW)
    p.cam_pivot.rotation_y = d.get('camera_yaw', p.rotation_y)
    p.cam_pivot.position = p.position + Vec3(0, 2.2, 0)

    # mundo (so se o mapa for o mesmo que gerou o save)
    w = data.get('world', {})
    nodes = game.world.nodes
    if w.get('seed') == WORLD_SEED and w.get('node_count') == len(nodes):
        changed = set()
        for index, hits_left, regrow in w.get('nodes', []):
            if 0 <= index < len(nodes):
                node = nodes[index]
                node.hits_left = max(0, min(node.max_hits, int(hits_left)))
                if node.hits_left <= 0:
                    node.depleted = True
                    node.visible = False
                    node.regrow_timer = max(0.0, float(regrow))
                    if node.obstacle:
                        node.obstacle.active = False
                    changed.add(node.chunk)
        for chunk in changed:
            chunk.rebuild()
    for x, y, z, value, age in w.get('coins', []):
        coin = Coin(game, Vec3(x, 0, z), int(value))
        coin.position = Vec3(x, y, z)
        coin.landed = True
        coin.age = float(age)

    story = data.get('story', {})
    game.intro_done = bool(story.get('intro_done', True))
    game.set_objective(str(story.get('objective', '')))

    game.play_time = float(data.get('play_time', 0))
    if not data.get('music_on', True) and game.music.enabled:
        game.music.toggle()
    game.hud.refresh(p)
