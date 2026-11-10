"""Collect news candidates from RSS feeds and other free sources.

Output: candidates JSON printed to stdout (list of {title, url, source, summary?}).
"""
import argparse
import json
import re
import sys
from html import unescape

import feedparser
import requests

from common import load_station, log

UA = "radio-station/1.0 (+personal news radio)"
TIMEOUT = 20


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def fetch_rss(feed: dict) -> list[dict]:
    try:
        parsed = feedparser.parse(requests.get(feed["url"], headers={"User-Agent": UA}, timeout=TIMEOUT).content)
    except Exception as e:
        log(f"rss fail {feed['name']}: {e}")
        return []
    items = []
    for e in parsed.entries[: feed.get("max", 10)]:
        items.append({
            "title": clean(getattr(e, "title", "")),
            "url": getattr(e, "link", ""),
            "source": feed["name"],
            "summary": clean(getattr(e, "summary", ""))[:300] or None,
        })
    return items


def fetch_hn(max_items: int) -> list[dict]:
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search",
                         params={"tags": "front_page"}, timeout=TIMEOUT).json()
    except Exception as e:
        log(f"hn fail: {e}")
        return []
    items = []
    for h in r.get("hits", [])[:max_items]:
        if h.get("title") and (h.get("url") or h.get("story_text")):
            items.append({
                "title": clean(h["title"]),
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                "source": "Hacker News",
                "summary": f"{h.get('points', 0)} points",
            })
    return items


def dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for it in items:
        key = re.sub(r"\W+", "", it["title"].lower())[:60]
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write candidates JSON here instead of stdout")
    args = ap.parse_args()

    st = load_station()
    items = []
    for feed in st["sources"].get("rss", []):
        items += fetch_rss(feed)
    hn = st["sources"].get("hn_frontpage", {})
    if hn.get("enabled"):
        items += fetch_hn(hn.get("max", 10))

    items = dedupe([i for i in items if i["title"] and i["url"]])
    log(f"collected {len(items)} candidates")
    data = json.dumps(items, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(data)
    else:
        sys.stdout.write(data)


if __name__ == "__main__":
    main()
