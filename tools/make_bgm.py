"""Generate a subtle ambient BGM loop (no external files needed).

Produces a seamless loop of slow-evolving soft pads — calm enough to sit
under speech. Replace bgm/morning.mp3 with any royalty-free track anytime.

Usage: ../.venv/bin/python make_bgm.py [seconds] [out.mp3]
"""
import sys
from pathlib import Path

import lameenc
import numpy as np

SR = 24000
SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent.parent / "bgm" / "morning.mp3"

# ゆったりした和音進行 (Am7 -> F -> C -> G) の柔らかいパッド
CHORDS = [
    [220.0, 261.63, 329.63, 392.0],    # Am7
    [174.61, 220.0, 261.63, 349.23],   # F
    [196.0, 261.63, 329.63, 392.0],    # C
    [196.0, 246.94, 293.66, 392.0],    # G
]

def synth(dur: float) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    chord_len = dur / len(CHORDS)
    out = np.zeros_like(t)
    rng = np.random.default_rng(7)
    for ci, chord in enumerate(CHORDS):
        seg = (t >= ci * chord_len) & (t < (ci + 1) * chord_len)
        tt = t[seg]
        # 各和音はゆるい立ち上がり/下がりでクロスフェード
        pos = (tt - ci * chord_len) / chord_len
        env = np.sin(np.pi * pos) ** 1.5
        sig = np.zeros_like(tt)
        for f in chord:
            # 微細なデチューンで音を柔らかく
            sig += np.sin(2 * np.pi * (f + rng.uniform(-0.4, 0.4)) * tt + rng.uniform(0, 6.28))
            sig += 0.3 * np.sin(2 * np.pi * f * 2 * tt)
        out[seg] = sig * env / (len(chord) * 1.3)
    # ループ両端が滑らかに繋がるよう全面に緩いスウェル
    swell = 0.75 + 0.25 * np.sin(2 * np.pi * t / dur * 2)
    out *= swell
    return np.clip(out * 0.9, -1, 1)


pcm = (synth(SECONDS) * 32767).astype(np.int16)
enc = lameenc.Encoder()
enc.set_bit_rate(96)
enc.set_in_sample_rate(SR)
enc.set_channels(1)
enc.set_quality(2)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(enc.encode(pcm.tobytes()) + enc.flush())
print(f"{OUT} ({SECONDS}s loop)")
