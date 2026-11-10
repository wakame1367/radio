"""Daily orchestrator: collect -> script -> assemble -> publish.

Usage: python run_daily.py [--date YYYY-MM-DD] [--script MODE] [--skip-publish]

--script:
  auto      GEMINI_API_KEY があればGemini、なければ定型台本 (デフォルト)
  template  常に定型台本
  gemini    常にGemini (キー必須)
  external  episodes/<date>.json は外部サービスが用意済み → 収集・生成をスキップ
  none      台本も音声も作らず publish だけ回す
Env: GEMINI_API_KEY (script=auto/gemini のとき)
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from common import episode_path, log, today_jst

HERE = Path(__file__).resolve().parent
PY = sys.executable


def step(*args):
    log(">>>", " ".join(str(a) for a in args))
    subprocess.run([PY, *map(str, args)], cwd=HERE, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=today_jst())
    ap.add_argument("--script", default="auto",
                    choices=["auto", "template", "gemini", "external", "none"])
    ap.add_argument("--skip-publish", action="store_true")
    args = ap.parse_args()

    mode = args.script
    if mode == "auto" and episode_path(args.date).exists():
        log(f"{args.date}: 台本が既に存在 → external モード")
        mode = "external"

    if mode in ("auto", "template", "gemini"):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            cand = tf.name
        step("collect.py", "--out", cand)
        env_extra = [] if mode == "auto" else ["--mode", mode]
        step("script.py", "--date", args.date, "--candidates", cand, *env_extra)
    elif mode == "external" and not episode_path(args.date).exists():
        sys.exit(f"external モードだが {episode_path(args.date)} がありません")

    if mode != "none":
        step("assemble.py", "--date", args.date)
    if not args.skip_publish:
        step("publish.py")
    log(f"done: {args.date} (script={mode})")


if __name__ == "__main__":
    main()
