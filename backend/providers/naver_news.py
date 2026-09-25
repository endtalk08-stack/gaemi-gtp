"""NAVER API HUB News Search provider.

Responsibility:
- Call NAVER API HUB only.
- Return source-shaped raw records.
- Do NOT classify, rank, deduplicate, format time, or decide UI behavior.
"""

import json
import os
import urllib.parse
import urllib.request


NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "").strip().strip("'\"")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "").strip().strip("'\"")
NAVER_NEWS_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"
REQUEST_TIMEOUT = 2.2


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
        "format": "json",
    })

    req = urllib.request.Request(
        f"{NAVER_NEWS_URL}?{params}",
        headers={
            "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
            "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET,
            "User-Agent": "gaemiGTP/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
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
