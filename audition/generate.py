"""Generate TTS audition samples for voice selection.

Usage:
    ../.venv/bin/python generate.py            # all engines
    ../.venv/bin/python generate.py voicevox   # one engine
"""
import io
import json
import sys
import wave
from pathlib import Path

import lameenc
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
OUT = Path(__file__).resolve().parent / "samples"
OUT.mkdir(exist_ok=True)
TEXT = (Path(__file__).resolve().parent / "sample_script.txt").read_text(encoding="utf-8").strip()
SR = 24000


def wav_bytes_to_int16(wav_bytes: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(wav_bytes)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def float_to_int16(x: np.ndarray) -> np.ndarray:
    return np.clip(x * 32767.0, -32768, 32767).astype(np.int16)


def to_mp3(pcm: np.ndarray, path: Path, sample_rate: int = SR):
    enc = lameenc.Encoder()
    enc.set_bit_rate(96)
    enc.set_in_sample_rate(sample_rate)
    enc.set_channels(1)
    enc.set_quality(2)
    data = enc.encode(pcm.tobytes()) + enc.flush()
    path.write_bytes(data)


def gen_voicevox() -> list[dict]:
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile

    so = str(MODELS / "voicevox_onnxruntime-linux-x64-1.23.2" / "lib" / "libvoicevox_onnxruntime.so.1.23.2")
    Onnxruntime.load_once(filename=so)
    ort = Onnxruntime.get()
    jtalk = OpenJtalk(str(MODELS / "open_jtalk_dic_utf_8-1.11"))
    synth = Synthesizer(ort, jtalk)
    model = VoiceModelFile.open(str(MODELS / "vvm" / "0.vvm"))
    synth.load_voice_model(model)

    # styles worth auditioning: ノーマル系のみ
    picks = []
    for meta in model.metas:
        for style in meta.styles:
            if style.name in ("ノーマル", "ふつう", "蕾"):
                picks.append((meta.name, style.name, style.id))
    results = []
    for name, style_name, sid in picks:
        out = OUT / f"vv_{name}_{style_name}.mp3"
        wav = synth.tts(TEXT, sid)
        to_mp3(wav_bytes_to_int16(wav), out)
        results.append({"file": f"samples/{out.name}", "engine": "VOICEVOX",
                        "voice": f"{name} ({style_name})", "credit": "要クレジット表記"})
        print("done", out.name, flush=True)
    return results


def gen_kokoro() -> list[dict]:
    from kokoro_onnx import Kokoro

    k = Kokoro(str(MODELS / "kokoro" / "kokoro-v1.0.onnx"),
               str(MODELS / "kokoro" / "voices-v1.0.bin"))
    results = []
    for voice in ["jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo"]:
        out = OUT / f"ko_{voice}.mp3"
        samples, sr = k.create(TEXT, voice=voice, speed=1.0, lang="ja")
        to_mp3(float_to_int16(samples), out, sr)
        results.append({"file": f"samples/{out.name}", "engine": "Kokoro",
                        "voice": voice, "credit": "クレジット不要 (Apache/MIT系)"})
        print("done", out.name, flush=True)
    return results


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    new = []
    if which in ("all", "voicevox"):
        new += gen_voicevox()
    if which in ("all", "kokoro"):
        new += gen_kokoro()
    mf = Path(__file__).resolve().parent / "manifest.json"
    old = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else []
    manifest = {e["file"]: e for e in old}
    manifest.update({e["file"]: e for e in new})
    mf.write_text(json.dumps(list(manifest.values()), ensure_ascii=False, indent=2),
                  encoding="utf-8")
    print(f"{len(new)} new, {len(manifest)} total -> {OUT}")
