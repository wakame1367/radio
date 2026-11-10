"""Generate the episode script (台本) with Gemini.

Input : candidates JSON (from collect.py)
Output: episodes/<date>.json  (format: radio/episode-1, without timing fields)
"""
import argparse
import json
import os
import sys

from common import episode_path, load_station, log, today_jst

MODEL = "gemini-2.5-flash"

PROMPT = """あなたは朝のニュースラジオ番組の放送作家です。
以下は今集めたニュース候補の一覧です。この中からバランスよく{news_count}件を選び、聴き取りやすい番組の台本をJSONで書いてください。

番組の方針: {style}

## 出力JSONの形
{{
  "title": "番組タイトル（日付なし。例: 半導体株上昇と生成AIの一週間）",
  "opening": [{{"say": "…", "show": "…"}}],
  "news": [
    {{
      "label": "短い見出し(10字前後)",
      "points": ["要点1", "要点2"],
      "lines": [{{"say": "…", "show": "…"}}],
      "url": "出典URL（候補一覧のものをそのまま）"
    }}
  ],
  "closing": [{{"say": "…", "show": "…"}}]
}}

## ルール
- say は音声合成で読む文。英字の固有名詞・サービス名はカタカナ読みにする（例: OpenAI→オープンエーアイ、GitHub→ギットハブ）。数字は漢数字や読みに直す（例: 3.5%→さんてんごパーセント）。記号は読みに変える
- show は字幕用の普通の表記（英字はそのまま）
- opening は挨拶+今日のラインナップ予告を2〜3文
- 各ニュースの lines は3〜5文。1文目で結論、あとで少し詳しく。要点 points は各2〜3個、名詞止めで短く
- 事実は候補のtitle/summaryに書いてあることだけ。推測・脚色・過去の知識の付け足しは禁止
- url は候補のものをそのまま写す。候補にないニュースは作らない
- closing は締めの挨拶1〜2文（明日も…等）
- 重複する話題は1件にまとめる。ジャンルはできるだけ散らす（政治経済/テック/ネットの話題/サイエンス等）
- 出力はJSONのみ。説明文やmarkdownの囲みは不要

## 候補一覧
{candidates}
"""


def build_episode(date: str, candidates: list[dict]) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY is not set")
    from google import genai
    from google.genai import types

    st = load_station()
    client = genai.Client(api_key=api_key)
    prompt = PROMPT.format(
        news_count=st["episode"]["news_count"],
        style=st["episode"]["style"],
        candidates=json.dumps(candidates, ensure_ascii=False, indent=1),
    )
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4,
        ),
    )
    body = json.loads(resp.text)

    ep = {
        "format": "radio/episode-1",
        "date": date,
        "title": body["title"],
        "opening": body["opening"],
        "news": body["news"],
        "closing": body["closing"],
    }
    # 出典のないニュースを弾き、候補由来のリンクカード情報を付ける
    by_url = {c["url"]: c for c in candidates}
    kept = []
    for n in ep["news"]:
        c = by_url.get(n.get("url"))
        if not c:
            continue
        from urllib.parse import urlparse
        n["link"] = {"url": c["url"], "title": c["title"],
                     "site": urlparse(c["url"]).netloc}
        kept.append(n)
    ep["news"] = kept
    return ep


def all_lines(ep: dict):
    for line in ep["opening"]:
        yield "opening", -1, line
    for i, n in enumerate(ep["news"]):
        for line in n["lines"]:
            yield "news", i, line
    for line in ep["closing"]:
        yield "closing", -1, line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=today_jst())
    ap.add_argument("--candidates", required=True, help="candidates JSON file")
    ap.add_argument("--out", help="default episodes/<date>.json")
    args = ap.parse_args()

    candidates = json.load(open(args.candidates, encoding="utf-8"))
    ep = build_episode(args.date, candidates)
    n_lines = sum(1 for _ in all_lines(ep))
    log(f"script: {len(ep['news'])} news, {n_lines} lines")

    out = args.out or episode_path(args.date)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(ep, f, ensure_ascii=False, indent=2)
    print(out)


if __name__ == "__main__":
    main()
