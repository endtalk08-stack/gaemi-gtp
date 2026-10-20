"""One-shot NVDA August 26 2026 earnings news-body audit, read-only.

Only one GET to Alpaca news. No provider integration, writes, orders or restarts.
Secrets only read through the existing isolated alpaca-news-verify gateway.
Print at most 8 short matched English headline/excerpt pairs.
"""
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
        print("ALPACA_EARNINGS_ERROR=credentials_missing", flush=True)
        return 2

    params = urllib.parse.urlencode({
        "symbols": "NVDA",
        "start": "2026-08-26T20:20:00Z",
        "end": "2026-08-27T12:00:00Z",
        "limit": 50,
        "sort": "asc",
        "include_content": "true",
        "exclude_contentless": "true",
    })
    url = "https://data.alpaca.markets/v1beta1/news?" + params
    request = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Accept": "application/json",
        "User-Agent": "gaemi-gtp-one-shot-earnings-audit/1.0",
    }, method="GET")
    print("ALPACA_EARNINGS_SCOPE=NVDA_2026_08_26_post_release_one_GET_50_max", flush=True)
    try:
        with urllib.request.urlopen(request, timeout=17) as resp:
            payload = json.loads(resp.read(700000))
    except urllib.error.HTTPError as exc:
        print("ALPACA_EARNINGS_ERROR=http_" + str(int(exc.code)), flush=True)
        return 3
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        print("ALPACA_EARNINGS_ERROR=transport_or_response", flush=True)
        return 4
    if not isinstance(payload, dict) or not isinstance(payload.get("news"), list):
        print("ALPACA_EARNINGS_ERROR=unexpected_schema", flush=True)
        return 5

    articles = payload["news"][:50]
    print("ALPACA_EARNINGS_FETCHED=" + str(len(articles)), flush=True)
    print("ALPACA_EARNINGS_HAS_NEXT_PAGE=" + str(bool(payload.get("next_page_token"))).lower(), flush=True)
    n_body, n_earnings, n_printed = 0, 0, 0
    for article in articles:
        if not isinstance(article, dict) or "NVDA" not in (article.get("symbols") or []):
            continue
        body = clean(article.get("content"))
        title = clean(article.get("headline"))
        if len(body) >= 500:
            n_body += 1
        if not re.search(r"nvidia|nvda", title, flags=re.I):
            continue
        if not re.search(r"earnings|revenue|EPS|quarter|outlook|guidance|results|profit|beat|forecast", title, flags=re.I):
            continue
        n_earnings += 1
        if n_printed >= 8:
            continue
        excerpt = ""
        evidence = {}
        for field, pat in [
            ("revenue", r"\brevenue\b"), ("EPS", r"\b(?:EPS|earnings per share)\b"),
            ("guidance", r"\b(?:guidance|forecast|outlook)\b"),
            ("data_center", r"\bdata\s+center\b"),
        ]:
            match = re.search(pat, body, flags=re.I)
            evidence[field] = bool(match)
            if match and not excerpt:
                excerpt = body[max(0,match.start()-45): min(len(body),match.start()+140)]
        n_printed += 1
        print("ALPACA_EARNINGS_ARTICLE=" + json.dumps({
            "published_utc": str(article.get("created_at") or "")[:40],
            "source": str(article.get("source") or "")[:40],
            "title_en": title[:220],
            "body_chars": len(body),
            "body_words": len(body.split()),
            "has": evidence,
            "excerpt_en": excerpt[:185],
            "url": str(article.get("url") or "")[:400],
        }, ensure_ascii=False), flush=True)
    print("ALPACA_EARNINGS_BODY_500PLUS=" + str(n_body), flush=True)
    print("ALPACA_EARNINGS_HEADLINE_MATCHES=" + str(n_earnings), flush=True)
    print("ALPACA_EARNINGS_TEST_COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
