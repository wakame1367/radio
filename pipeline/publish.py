"""Build the public site into dist/ and update episodes.json.

- episodes.json: newest-first index {date, title, seconds}
- dist/: site/ + station.json + episodes.json + episodes/*.json + last keep_days of audio
- Audio is never committed to main; only dist content goes to gh-pages.
"""
import argparse
import json
import shutil
from datetime import timedelta

from common import AUDIO_DIR, DIST_DIR, EPISODES_DIR, ROOT, SITE_DIR, load_station, log, parse_date, today_jst


def build_index(st: dict) -> list[dict]:
    eps = []
    for f in sorted(EPISODES_DIR.glob("*.json"), reverse=True):
        try:
            ep = json.loads(f.read_text(encoding="utf-8"))
            eps.append({"date": ep["date"], "title": ep["title"],
                        "seconds": ep.get("seconds", 0)})
        except Exception as e:
            log(f"skip {f.name}: {e}")
    return eps


def collect_audio(st: dict) -> set[str]:
    keep = st["audio"]["keep_days"]
    cutoff = parse_date(today_jst()) - timedelta(days=keep)
    out = set()
    for p in AUDIO_DIR.glob("*.mp3"):
        try:
            if parse_date(p.stem) >= cutoff:
                out.add(p.stem)
        except ValueError:
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="only rebuild episodes.json + dist, no push")
    args = ap.parse_args()

    st = load_station()
    index = build_index(st)
    (ROOT / "episodes.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"episodes.json: {len(index)} entries")

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()
    shutil.copytree(SITE_DIR, DIST_DIR, dirs_exist_ok=True)
    for name in ("station.json", "episodes.json"):
        shutil.copy2(ROOT / name, DIST_DIR / name)
    shutil.copytree(EPISODES_DIR, DIST_DIR / "episodes")

    keep = collect_audio(st)
    (DIST_DIR / "audio").mkdir()
    for d in keep:
        src = AUDIO_DIR / f"{d}.mp3"
        if src.exists():
            shutil.copy2(src, DIST_DIR / "audio" / src.name)
    log(f"dist ready: {len(index)} episodes, {len(keep)} audio files")


if __name__ == "__main__":
    main()
