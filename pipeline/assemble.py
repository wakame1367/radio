"""Synthesize every line, concatenate with pauses, compute timing,
mix BGM with ducking, encode to mp3, and finalize the episode JSON.

Usage: python assemble.py --date 2026-11-09 [--dry]
"""
import argparse
import json
from datetime import datetime, timezone

import lameenc
import numpy as np

from common import audio_path, episode_path, load_station, log
from script import all_lines
from voice import SAMPLE_RATE, get_engine

GAP_LINE = 0.35        # 同一パート内の行間
GAP_PART = 0.9         # opening→news / news→closing
GAP_NEWS = 0.75        # ニュース項目どうし
TAIL_SECONDS = 3.0     # 音声の後に残すBGMの尻
BGM_FADE_IN = 1.2
BGM_FADE_OUT = 2.5


def silence(sec: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * sec), dtype=np.int16)


def synth_episode(ep: dict, engine) -> np.ndarray:
    """Returns concatenated voice PCM. Fills ep['lines_timed'] and ep['segments']."""
    chunks, lines_timed, segments = [], [], []
    t = 0.0
    prev_key = None
    seg_start = 0.0
    seg_key = None

    def close_segment():
        nonlocal seg_key
        if seg_key is not None:
            kind, idx = seg_key
            segments.append({"kind": kind, "index": idx, "start": round(seg_start, 3),
                             "end": round(t, 3)})
            seg_key = None

    for kind, idx, line in all_lines(ep):
        key = (kind, idx)
        if prev_key is not None:
            same_part = key == prev_key
            gap = GAP_LINE if same_part else (GAP_NEWS if kind == "news" else GAP_PART)
            chunks.append(silence(gap))
            t += gap
        if key != seg_key:
            close_segment()
            seg_key = key
            seg_start = t
        pcm = engine.synth(line["say"])
        dur = len(pcm) / SAMPLE_RATE
        chunks.append(pcm)
        part = kind if idx < 0 else f"{kind}:{idx}"
        lines_timed.append({"start": round(t, 3), "end": round(t + dur, 3),
                            "show": line["show"], "part": part})
        t += dur
        prev_key = key
    close_segment()

    ep["lines_timed"] = lines_timed
    ep["segments"] = segments
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)


def normalize(pcm: np.ndarray, peak: float = 0.85) -> np.ndarray:
    m = np.abs(pcm).max()
    if m == 0:
        return pcm
    return (pcm.astype(np.float64) * (peak * 32767 / m)).clip(-32768, 32767).astype(np.int16)


def mix_bgm(voice: np.ndarray, bgm_path, vol: float) -> np.ndarray:
    import miniaudio

    dec = miniaudio.decode_file(str(bgm_path), output_format=miniaudio.SampleFormat.SIGNED16,
                                nchannels=1, sample_rate=SAMPLE_RATE)
    bgm = np.frombuffer(dec.samples, dtype=np.int16).astype(np.float64)

    n_voice = len(voice)
    n_tail = int(TAIL_SECONDS * SAMPLE_RATE)
    n = n_voice + n_tail
    if len(bgm) < n:
        bgm = np.tile(bgm, int(np.ceil(n / len(bgm))))
    bgm = bgm[:n].copy()

    # 発声区間を検出(50ms窓のRMS)
    win = int(0.05 * SAMPLE_RATE)
    v = voice.astype(np.float64) / 32767.0
    pad = np.pad(v, (0, win - len(v) % win))
    rms = np.sqrt((pad.reshape(-1, win) ** 2).mean(axis=1))
    mask = np.repeat(rms > 0.01, win)[:n_voice]

    # 目標ゲイン: 発声中は vol、無音部は vol*2.2。滑らかに追従(攻100ms/放700ms)
    target = np.where(mask, vol, min(vol * 2.2, 0.4))
    gain = np.empty(n_voice)
    g = vol
    a_up = 1 - np.exp(-1 / (0.7 * SAMPLE_RATE))
    a_dn = 1 - np.exp(-1 / (0.1 * SAMPLE_RATE))
    for i in range(n_voice):
        a = a_dn if target[i] < g else a_up
        g += (target[i] - g) * a
        gain[i] = g
    gain = np.concatenate([gain, np.full(n_tail, vol)])

    fi = int(BGM_FADE_IN * SAMPLE_RATE)
    fo = int(BGM_FADE_OUT * SAMPLE_RATE)
    gain[:fi] *= np.linspace(0, 1, fi)
    gain[-fo:] *= np.linspace(1, 0, fo)

    voice_full = np.concatenate([voice.astype(np.float64), np.zeros(n_tail)])
    out = voice_full + bgm * gain
    return np.clip(out, -32768, 32767).astype(np.int16)


def encode_mp3(pcm: np.ndarray, path) -> float:
    enc = lameenc.Encoder()
    enc.set_bit_rate(96)
    enc.set_in_sample_rate(SAMPLE_RATE)
    enc.set_channels(1)
    enc.set_quality(2)
    data = enc.encode(pcm.tobytes()) + enc.flush()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return len(pcm) / SAMPLE_RATE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--no-bgm", action="store_true")
    args = ap.parse_args()

    st = load_station()
    ep_file = episode_path(args.date)
    ep = json.loads(ep_file.read_text(encoding="utf-8"))

    engine = get_engine(st)
    voice = synth_episode(ep, engine)
    voice = normalize(voice)

    bgm = st.get("bgm", {})
    if bgm.get("enabled") and not args.no_bgm:
        from common import ROOT
        f = ROOT / bgm["file"]
        if f.exists():
            log("mixing bgm")
            pcm = mix_bgm(voice, f, bgm.get("volume", 0.14))
        else:
            log(f"bgm missing: {f} (voice only)")
            pcm = np.concatenate([voice, silence(TAIL_SECONDS)])
    else:
        pcm = np.concatenate([voice, silence(TAIL_SECONDS)])

    seconds = encode_mp3(pcm, audio_path(args.date))
    ep["seconds"] = round(seconds, 1)
    ep["made_at"] = datetime.now(timezone.utc).isoformat()
    ep_file.write_text(json.dumps(ep, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"{args.date}: {seconds:.0f}s -> {audio_path(args.date)}")


if __name__ == "__main__":
    main()
