"""One-time Alpaca NVDA news-body audit, read-only.

Only GET /v1beta1/news; no orders, no DB writes, no news-worker integration.
Outputs bounded metadata + at most three short English previews, never credentials.
"""
import datetime as dt
import html
from html.parser import HTMLParser
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "div", "br", "li"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in ("p", "div", "li"):
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def clean(value):
    parser = _Text()
    parser.feed(str(value or "")[:100000])
    return re.sub(r"\s+", " ", html.unescape("".join(parser.parts))).strip()


def main():
    key = os.getenv("APCA_API_KEY_ID", "").strip()
    secret = os.getenv("APCA_API_SECRET_KEY", "").strip()
    if not key or not secret:
        print("ALPACA_NEWS_ERROR=credentials_missing", flush=True)
        return 2
    day = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).date()
    params = urllib.parse.urlencode({
        "symbols": "NVDA",
        "start": day.isoformat(),
        "limit": 10,
        "sort": "desc",
        "include_content": "true",
        "exclude_contentless": "true",
    })
    url = "https://data.alpaca.markets/v1beta1/news?" + params
    req = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Accept": "application/json",
        "User-Agent": "gaemi-gtp-news-body-audit/1.0",
    }, method="GET")
    print("ALPACA_NEWS_SCOPE=NVDA_last_7_days_one_GET_content_required", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read(400000))
    except urllib.error.HTTPError as exc:
        print("ALPACA_NEWS_ERROR=http_" + str(int(exc.code)), flush=True)
        return 3
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        print("ALPACA_NEWS_ERROR=transport_or_response", flush=True)
        return 4
    if not isinstance(payload, dict) or not isinstance(payload.get("news"), list):
        print("ALPACA_NEWS_ERROR=unexpected_schema", flush=True)
        return 5
    articles = payload["news"][:10]
    print("ALPACA_NEWS_COUNT=" + str(len(articles)), flush=True)
    body_count = 0
    long_count = 0
    for i, article in enumerate(articles):
        if not isinstance(article, dict):
            continue
        symbols = article.get("symbols") or []
        if "NVDA" not in symbols:
            print("ALPACA_NEWS_NON_NVDA_SKIPPED", flush=True)
            continue
        body = clean(article.get("content"))
        summary = clean(article.get("summary"))
        if body:
            body_count += 1
        if len(body) >= 500:
            long_count += 1
        result = {
            "idx": i + 1,
            "source": str(article.get("source") or "")[:70],
            "time_utc": str(article.get("created_at") or "")[:35],
            "headline_en": clean(article.get("headline"))[:220],
            "summary_chars": len(summary),
            "body_chars": len(body),
            "body_words": len(body.split()),
            "article_url": str(article.get("url") or "")[:450],
        }
        if i < 3 and body:
            # Preview is deliberately short, not a copy of the full article.
            result["body_preview_en"] = body[:170]
        print("ALPACA_NEWS_ITEM=" + json.dumps(result, ensure_ascii=False), flush=True)
    print("ALPACA_NEWS_BODY_PRESENT=" + str(body_count), flush=True)
    print("ALPACA_NEWS_BODY_500PLUS=" + str(long_count), flush=True)
    print("ALPACA_NEWS_TEST_COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
