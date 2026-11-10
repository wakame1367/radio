"""Daily orchestrator: collect -> script -> assemble -> publish.

Usage: python run_daily.py [--date YYYY-MM-DD] [--skip-publish]
Env:    GEMINI_API_KEY (for script.py)
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from common import log, today_jst

HERE = Path(__file__).resolve().parent
PY = sys.executable


def step(*args):
    log(">>>", " ".join(str(a) for a in args))
    subprocess.run([PY, *map(str, args)], cwd=HERE, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=today_jst())
    ap.add_argument("--skip-publish", action="store_true")
    args = ap.parse_args()

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        cand = tf.name
    step("collect.py", "--out", cand)
    step("script.py", "--date", args.date, "--candidates", cand)
    step("assemble.py", "--date", args.date)
    if not args.skip_publish:
        step("publish.py")
    log(f"done: {args.date}")


if __name__ == "__main__":
    main()
