"""Shared config/paths for the daily pipeline."""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "episodes"
AUDIO_DIR = ROOT / "audio"
MODELS_DIR = ROOT / "models"
SITE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"


def load_station() -> dict:
    return json.loads((ROOT / "station.json").read_text(encoding="utf-8"))


def episode_path(d: str) -> Path:
    return EPISODES_DIR / f"{d}.json"


def audio_path(d: str) -> Path:
    return AUDIO_DIR / f"{d}.mp3"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def today_jst() -> str:
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=9))).date().isoformat()


def parse_date(s: str) -> date:
    return date.fromisoformat(s)
