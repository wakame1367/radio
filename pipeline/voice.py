"""TTS backends. Each engine exposes synth(text) -> int16 mono PCM @ SAMPLE_RATE.

Engine is chosen by station.json voice.engine. All engines run on CPU.
"""
import io
import wave
from pathlib import Path

import numpy as np

from common import MODELS_DIR, load_station, log

SAMPLE_RATE = 24000


def wav_to_int16(wav_bytes: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(wav_bytes)) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() > 1:
            pcm = pcm.reshape(-1, w.getnchannels()).mean(axis=1).astype(np.int16)
        return pcm


class Engine:
    def synth(self, text: str) -> np.ndarray:
        raise NotImplementedError


class VoicevoxEngine(Engine):
    """voicevox_core wheel + voicevox_onnxruntime + VVM models."""

    def __init__(self, cfg: dict):
        from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile

        ort_dir = sorted(MODELS_DIR.glob("voicevox_onnxruntime-*/lib/libvoicevox_onnxruntime.so.*"))
        so = next((p for p in ort_dir if p.name.count(".") == 3), ort_dir[0])
        Onnxruntime.load_once(filename=str(so))
        self.synth_ = Synthesizer(Onnxruntime.get(), OpenJtalk(str(MODELS_DIR / "open_jtalk_dic_utf_8-1.11")))
        for vvm in sorted(MODELS_DIR.glob("vvm/*.vvm")):
            self.synth_.load_voice_model(VoiceModelFile.open(str(vvm)))
        self.style_id = cfg["style_id"]
        self.speed = cfg.get("speed", 1.0)

    def synth(self, text: str) -> np.ndarray:
        if self.speed != 1.0:
            q = self.synth_.create_audio_query(text, self.style_id)
            q.speed_scale = self.speed
            wav = self.synth_.synthesis(q, self.style_id)
        else:
            wav = self.synth_.tts(text, self.style_id)
        return wav_to_int16(wav)


class KokoroEngine(Engine):
    """kokoro-onnx, Japanese voices jf_*/jm_*. Needs models/kokoro/."""

    def __init__(self, cfg: dict):
        from kokoro_onnx import Kokoro

        self.k = Kokoro(str(MODELS_DIR / "kokoro" / "kokoro-v1.0.onnx"),
                        str(MODELS_DIR / "kokoro" / "voices-v1.0.bin"))
        self.voice = cfg.get("voice", "jf_alpha")
        self.speed = cfg.get("speed", 1.0)

    def synth(self, text: str) -> np.ndarray:
        samples, _sr = self.k.create(text, voice=self.voice, speed=self.speed, lang="ja")
        return np.clip(samples * 32767.0, -32768, 32767).astype(np.int16)


class OndokuLikeApiEngine(Engine):
    """OpenAI-compatible /v1/audio/speech endpoint (e.g. AivisSpeech engine, OpenAI TTS).

    cfg: {endpoint, model, voice, api_key_env?, speed?}
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def synth(self, text: str) -> np.ndarray:
        import os
        import requests
        import miniaudio

        headers = {}
        if self.cfg.get("api_key_env"):
            headers["Authorization"] = f"Bearer {os.environ[self.cfg['api_key_env']]}"
        r = requests.post(
            self.cfg["endpoint"],
            json={"model": self.cfg["model"], "voice": self.cfg["voice"],
                  "input": text, "response_format": "mp3",
                  "speed": self.cfg.get("speed", 1.0)},
            headers=headers, timeout=120)
        r.raise_for_status()
        dec = miniaudio.decode(r.content, output_format=miniaudio.SampleFormat.SIGNED16,
                               nchannels=1, sample_rate=SAMPLE_RATE)
        return np.frombuffer(dec.samples, dtype=np.int16)


ENGINES = {"voicevox": VoicevoxEngine, "kokoro": KokoroEngine, "api": OndokuLikeApiEngine}


def get_engine(st: dict | None = None) -> Engine:
    st = st or load_station()
    cfg = st["voice"]
    log(f"tts engine: {cfg['engine']}")
    return ENGINES[cfg["engine"]](cfg)
