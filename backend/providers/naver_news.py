"""Naver News Search API provider.

Responsibility:
- Call Naver's API.
- Return source-shaped raw records.
- Do NOT classify, rank, deduplicate, format time, or decide UI behavior.
"""

import json
import os
import urllib.parse
import urllib.request


NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "").strip().strip("'\"")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "").strip().strip("'\"")


def is_configured():
    return bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)


def fetch_news(query, display=20):
    if not is_configured():
        return []

    params = urllib.parse.urlencode({
        "query": str(query or "").strip(),
        "display": max(1, min(int(display), 100)),
        "start": 1,
        "sort": "date",
    })
    url = f"https://openapi.naver.com/v1/search/news.json?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            "User-Agent": "gaemiGTP/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"[provider:naver-news] failed query={query}: {type(exc).__name__}: {exc}")
        return []

    rows = []
    for item in payload.get("items", []):
        rows.append({
            "provider": "naver",
            "raw_title": item.get("title", ""),
            "raw_source": "",
            "raw_pub_date": item.get("pubDate", ""),
            "raw_link": item.get("link", ""),
            "raw_original_link": item.get("originallink", ""),
        })
    return rows
