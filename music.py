"""Musica ambiente composta e sintetizada no codigo (nenhum arquivo baixado).

Tema "Vila de Carvalho": 120 BPM, Do maior, 24 compassos (48 s) que se repetem sem emenda.
  A (8 compassos)  tema principal ........ C  G  Am F  C  G  F  G
  B (8 compassos)  ponte, mais animada ... Am F  C  G  Am F  Dm G
  C (8 compassos)  resolucao ............. F  G  Em Am F  G  C  C
Instrumentos: bateria (bumbo, caixa, chimbal), baixo, acordes (pad), arpejo e melodia com eco.

A primeira vez que o jogo roda, a musica e gerada (~2 s) e salva em assets/; depois so e carregada.
Para mudar a musica, edite as listas abaixo e aumente VERSION (o arquivo e gerado de novo).
"""
import os
import wave
from pathlib import Path

import numpy as np
from ursina import Audio, curve

VERSION = 1
SAMPLE_RATE = 44100
BPM = 120
BEAT = SAMPLE_RATE * 60 // BPM          # 22050 amostras por batida (exato -> loop perfeito)
BAR = BEAT * 4
ASSETS = Path(__file__).resolve().parent / 'assets'
MUSIC_FILE = ASSETS / f'musica_vila_v{VERSION}.wav'

# ------------------------------------------------------------- composicao
# Acordes (notas MIDI do pad) e nota grave de cada acorde
CHORDS = {
    'C':  ((60, 64, 67), 36), 'G': ((59, 62, 67), 43), 'Am': ((57, 60, 64), 45),
    'F':  ((57, 60, 65), 41), 'Dm': ((57, 62, 65), 38), 'Em': ((55, 59, 64), 40),
}
PROGRESSION = (['C', 'G', 'Am', 'F', 'C', 'G', 'F', 'G'] +          # A
               ['Am', 'F', 'C', 'G', 'Am', 'F', 'Dm', 'G'] +       # B
               ['F', 'G', 'Em', 'Am', 'F', 'G', 'C', 'C'])         # C

# Melodia: por compasso, lista de (batida de inicio, duracao em batidas, nota MIDI)
MELODY = [
    # --- A: tema
    [(0, 1, 76), (1, .5, 79), (1.5, .5, 81), (2, 1, 79), (3, 1, 76)],
    [(0, 1.5, 74), (1.5, .5, 71), (2, 1, 74), (3, 1, 79)],
    [(0, 1, 72), (1, .5, 76), (1.5, .5, 79), (2, 1, 81), (3, 1, 76)],
    [(0, 1.5, 77), (1.5, .5, 76), (2, 1, 72), (3, 1, 69)],
    [(0, 1, 76), (1, .5, 79), (1.5, .5, 81), (2, 1, 84), (3, 1, 79)],
    [(0, 1, 83), (1, 1, 81), (2, 2, 79)],
    [(0, 1, 77), (1, .5, 81), (1.5, .5, 79), (2, 1, 77), (3, 1, 76)],
    [(0, 2, 74), (2, 1, 71), (3, 1, 74)],
    # --- B: ponte (mais ritmada)
    [(0, .5, 81), (.5, .5, 81), (1, .5, 79), (1.5, .5, 81), (2, 1, 84), (3, 1, 81)],
    [(0, .5, 77), (.5, .5, 77), (1, .5, 76), (1.5, .5, 77), (2, 1, 81), (3, 1, 77)],
    [(0, .5, 76), (.5, .5, 76), (1, .5, 74), (1.5, .5, 76), (2, 1, 79), (3, 1, 84)],
    [(0, 1.5, 83), (1.5, .5, 81), (2, 2, 79)],
    [(0, .5, 81), (.5, .5, 81), (1, .5, 79), (1.5, .5, 81), (2, 1, 84), (3, 1, 81)],
    [(0, .5, 77), (.5, .5, 81), (1, .5, 84), (1.5, .5, 81), (2, 2, 77)],
    [(0, 1, 74), (1, 1, 77), (2, 1, 81), (3, 1, 77)],
    [(0, 1, 79), (1, 1, 83), (2, 2, 86)],
    # --- C: resolucao
    [(0, 2, 84), (2, 1, 81), (3, 1, 77)],
    [(0, 2, 83), (2, 1, 79), (3, 1, 74)],
    [(0, 1.5, 79), (1.5, .5, 76), (2, 2, 71)],
    [(0, 1, 72), (1, 1, 76), (2, 2, 81)],
    [(0, 1, 77), (1, .5, 81), (1.5, .5, 84), (2, 1, 81), (3, 1, 77)],
    [(0, 1, 79), (1, .5, 83), (1.5, .5, 86), (2, 1, 83), (3, 1, 79)],
    [(0, 3, 84), (3, 1, 79)],
    [(0, 1, 76), (1, 1, 79), (2, 2, 72)],
]
assert len(MELODY) == len(PROGRESSION)

# Baixo: por compasso, (batida, intervalo em semitons a partir da nota grave)
BASS_PATTERN = [(0, 0), (1, 0), (1.5, 12), (2, 7), (3, 0), (3.5, 12)]
# Arpejo: indices nas notas do acorde (3 notas + oitava acima), em semicolcheias
ARP_PATTERN = [0, 1, 2, 3, 4, 3, 2, 1]


# ------------------------------------------------------------- sintese
def _freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _t(n):
    return np.arange(n) / SAMPLE_RATE


def _place(buf, start, sound):
    """Soma `sound` no buffer a partir de `start`, dando a volta no fim (loop sem emenda)."""
    start %= len(buf)
    end = start + len(sound)
    if end <= len(buf):
        buf[start:end] += sound
    else:
        cut = len(buf) - start
        buf[start:] += sound[:cut]
        buf[:end - len(buf)] += sound[cut:]


def _envelope(n, attack, release, sustain=1.0, decay=None):
    """Envelope simples: subida, (queda opcional) e soltura."""
    t = _t(n)
    env = np.minimum(1.0, t / max(attack, 1e-4))
    if decay:
        env *= sustain + (1 - sustain) * np.exp(-np.maximum(0, t - attack) / decay)
    rel = int(release * SAMPLE_RATE)
    if rel and rel < n:
        env[-rel:] *= np.linspace(1, 0, rel)
    return env


def _lead(midi, beats):
    """Flauta suave: senoide + harmonicos leves, com vibrato que entra devagar."""
    n = int(beats * BEAT)
    t = _t(n)
    f = _freq(midi)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.25)
    phase = 2 * np.pi * f * np.cumsum(vib) / SAMPLE_RATE
    wave_ = np.sin(phase) + 0.35 * np.sin(2 * phase) + 0.12 * np.sin(3 * phase)
    return wave_ * _envelope(n, 0.015, 0.06, sustain=0.75, decay=0.25)


def _pad(chord, beats):
    """Acorde sustentado e macio (ondas dente-de-serra suaves, levemente desafinadas)."""
    n = int(beats * BEAT)
    t = _t(n)
    out = np.zeros(n)
    for midi in chord:
        for detune in (0.997, 1.003):
            f = _freq(midi) * detune
            for k in range(1, 6):
                out += np.sin(2 * np.pi * f * k * t) / (k * k)
    return out * _envelope(n, 0.25, 0.35) / (len(chord) * 2)


def _bass(midi, beats):
    """Baixo arredondado (onda triangular) com ataque marcado."""
    n = int(beats * BEAT)
    t = _t(n)
    f = _freq(midi)
    out = np.zeros(n)
    for k, sign in ((1, 1), (3, -1), (5, 1), (7, -1)):
        out += sign * np.sin(2 * np.pi * f * k * t) / (k * k)
    out += 0.25 * np.sign(np.sin(2 * np.pi * f * t)) * np.exp(-t / 0.05)   # "estalo" do ataque
    return out * _envelope(n, 0.005, 0.04, sustain=0.55, decay=0.18)


def _pluck(midi, beats):
    """Nota dedilhada curta para o arpejo."""
    n = int(beats * BEAT)
    t = _t(n)
    f = _freq(midi)
    out = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) * np.exp(-t / 0.05)
    return out * np.exp(-t / 0.14) * _envelope(n, 0.003, 0.02)


def _kick():
    n = int(0.3 * SAMPLE_RATE)
    t = _t(n)
    f = 45 + 85 * np.exp(-t / 0.035)
    return np.sin(2 * np.pi * np.cumsum(f) / SAMPLE_RATE) * np.exp(-t / 0.11)


def _snare(rng):
    n = int(0.22 * SAMPLE_RATE)
    t = _t(n)
    noise = rng.uniform(-1, 1, n)
    noise = np.diff(noise, prepend=0) * 0.6 + noise * 0.4             # mais "brilho"
    return noise * np.exp(-t / 0.055) * 0.8 + np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05) * 0.5


def _hat(rng, open_=False):
    n = int((0.18 if open_ else 0.06) * SAMPLE_RATE)
    t = _t(n)
    noise = np.diff(rng.uniform(-1, 1, n + 1))                          # passa-altas simples
    return noise * np.exp(-t / (0.06 if open_ else 0.014))


def render():
    """Gera a musica inteira (mono, float entre -1 e 1)."""
    rng = np.random.default_rng(7)
    total = BAR * len(PROGRESSION)
    drums, bass, pad, arp, lead = (np.zeros(total) for _ in range(5))
    kick, snare = _kick(), _snare(rng)

    for bar, name in enumerate(PROGRESSION):
        chord, root = CHORDS[name]
        start = bar * BAR
        section = bar // 8                          # 0 = A, 1 = B, 2 = C
        last_of_section = bar % 8 == 7

        # bateria
        for beat in range(4):
            _place(drums, start + beat * BEAT, kick if beat in (0, 2) else snare * 0.55)
        if section == 1:                            # ponte: bumbo extra deixa mais "dancante"
            _place(drums, start + int(1.5 * BEAT), kick * 0.8)
            _place(drums, start + int(3.5 * BEAT), kick * 0.6)
        for eighth in range(8):
            open_ = section == 2 and eighth % 2 == 1
            _place(drums, start + eighth * BEAT // 2, _hat(rng, open_) * (0.22 if eighth % 2 else 0.12))
        if last_of_section:                         # virada: caixa em semicolcheias no fim da parte
            for s in range(4):
                _place(drums, start + 3 * BEAT + s * BEAT // 4, snare * (0.25 + 0.1 * s))

        # baixo
        for beat, interval in BASS_PATTERN:
            _place(bass, start + int(beat * BEAT), _bass(root + interval, 0.5))

        # acordes
        _place(pad, start, _pad(chord, 4))

        # arpejo (colcheias na parte A, semicolcheias na B e C)
        tones = list(chord) + [chord[0] + 12, chord[1] + 12]
        step = BEAT // 2 if section == 0 else BEAT // 4
        for i in range(BAR // step):
            note = tones[ARP_PATTERN[i % len(ARP_PATTERN)]] + 12
            _place(arp, start + i * step, _pluck(note, 0.5))

        # melodia
        for beat, dur, note in MELODY[bar]:
            _place(lead, start + int(beat * BEAT), _lead(note, dur))

    # eco na melodia (3/4 de batida), feito com rotacao -> continua sem emenda no loop
    delay = int(0.75 * BEAT)
    lead = lead + 0.32 * np.roll(lead, delay) + 0.12 * np.roll(lead, 2 * delay)

    mix = drums * 0.55 + bass * 0.42 + pad * 0.28 + arp * 0.10 + lead * 0.20
    mix = np.tanh(mix * 1.2)                        # compressao suave
    return mix / np.max(np.abs(mix)) * 0.85


def ensure_music_file():
    """Gera o arquivo da musica se ainda nao existir. Retorna o caminho."""
    if not MUSIC_FILE.exists():
        ASSETS.mkdir(exist_ok=True)
        data = (render() * 32767).astype(np.int16)
        tmp = MUSIC_FILE.with_suffix('.tmp')
        with wave.open(str(tmp), 'wb') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(SAMPLE_RATE)
            f.writeframes(data.tobytes())
        os.replace(tmp, MUSIC_FILE)
    return MUSIC_FILE


class MusicPlayer:
    """Toca a musica em loop no jogo: entra suave, abaixa na pausa/morte e liga/desliga com M."""

    def __init__(self, volume, quiet_volume):
        self.volume = volume
        self.quiet_volume = quiet_volume
        self.enabled = True
        self.quiet = False
        self.override = None     # volume forcado (ex.: cutscene em silencio); None = normal
        self.audio = None
        try:
            self.audio = Audio(ensure_music_file(), loop=True, volume=0, group='music', autoplay=True)
            self._apply(duration=2.5)     # entra suave
        except Exception as error:      # sem audio/numpy: o jogo continua, so que sem musica
            print('Musica desativada:', error)

    def _target(self):
        if not self.enabled:
            return 0
        if self.override is not None:
            return self.override
        return self.quiet_volume if self.quiet else self.volume

    def set_override(self, volume, duration=1.5):
        """Forca um volume (None volta ao normal)."""
        self.override = volume
        self._apply(duration)

    def _apply(self, duration=0.6):
        if self.audio:
            # (Audio.fade do Ursina 8.3 tem um bug nos argumentos; animate faz o mesmo)
            self.audio.animate('volume', self._target(), duration=duration, curve=curve.linear,
                               ignore_paused=True)

    def set_quiet(self, quiet):
        if quiet != self.quiet:
            self.quiet = quiet
            self._apply()

    def toggle(self):
        self.enabled = not self.enabled
        self._apply(0.4)
        return self.enabled


if __name__ == '__main__':
    # python music.py -> gera de novo o arquivo (util para ouvir enquanto edita a composicao)
    if MUSIC_FILE.exists():
        MUSIC_FILE.unlink()
    print('Gerado:', ensure_music_file())
