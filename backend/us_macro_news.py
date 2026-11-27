"""US macro headlines from primary sources, translated to Korean (no AI).

Every few minutes (gaemigtp-us-macro-news.timer):

  Fed / White House / economic-data RSS -> keep market-related items by fixed rules
  -> DeepL translates the headline only -> R2 news/macro/us/feed.json

The headline is shown as it is, only translated, with the original English title
and a link to the official page. Sources are US government publications.
Only new headlines are translated, so the free tiers are far more than enough.
DeepL (DEEPL_API_KEY, 500,000 characters a month free) is tried first; when it
fails or its monthly limit is used up, Google Translation (GOOGLE_TRANSLATE_API_KEY)
takes over. Without a working translator nothing is published and new items wait.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

STATE_PATH = Path("/var/lib/gaemigtp-news/us-macro-news-state.json")
OBJECT_KEY = "news/macro/us/feed.json"
KEEP_ITEMS = 200
MAX_AGE = dt.timedelta(days=3)
USER_AGENT = "Mozilla/5.0 (compatible; gaemiGTP-news/1.0)"

# Celebrations, ceremonies and people news that never move markets.
SKIP = re.compile(
    r"\b(day|week|month|anniversary|first lady|melania|turkey|pardon|honoring|honors|commemorat|"
    r"memorial|remembrance|heritage|thanksgiving|christmas|holiday|icymi|condolence|birthday|"
    r"medal|ceremony|clemency|capital sentences|killers)\b", re.I)
# White House news and statements: only economic and market topics.
MARKET = re.compile(
    r"\b(tariffs?|trade|china|chinese|export|import|sanction|semiconductor|chips?|energy|oil|gas|"
    r"lng|econom\w*|inflation|prices?|jobs|employment|wages?|tax|deficit|debt|budget|treasury|"
    r"federal reserve|fed|interest rates?|dollar|crypto\w*|bitcoin|stablecoin|stocks?|market|"
    r"invest\w*|manufactur\w*|steel|alumin\w*|auto\w*|pharma\w*|drug pric\w*|artificial intelligence|"
    r"ai|deal|agreement|deregulat\w*|regulat\w*|shutdown|minerals?|rare earth)\b", re.I)

# (source label, widget category, feed url, rule)
FEEDS = [
    ("연준", "연준·금리", "https://www.federalreserve.gov/feeds/press_monetary.xml", "all"),
    ("연준", "연준·금리", "https://www.federalreserve.gov/feeds/speeches.xml", "all"),
    ("연준", "연준·금리", "https://www.federalreserve.gov/feeds/testimony.xml", "all"),
    ("백악관", "정책·규제", "https://www.whitehouse.gov/presidential-actions/feed/", "skip"),
    ("백악관", "정책·규제", "https://www.whitehouse.gov/news/feed/", "market"),
    ("백악관", "정책·규제", "https://www.whitehouse.gov/briefings-statements/feed/", "market"),
    ("美 경제분석국", "경제지표", "https://apps.bea.gov/rss/rss.xml", "all"),
]


def fetch(url, timeout=20):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def keep(title, rule):
    if rule == "all":
        return True
    if SKIP.search(title):
        return False
    return rule == "skip" or bool(MARKET.search(title))


def parse_feed(raw, source, category, rule, now):
    root = ET.fromstring(raw)
    rows = []
    for item in root.iter("item"):
        title = clean(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "").astimezone(dt.timezone.utc)
        except (TypeError, ValueError):
            continue
        if not title or not link.startswith("https://") or now - published > MAX_AGE or published > now + dt.timedelta(hours=1):
            continue
        if not keep(title, rule):
            continue
        rows.append({"id": hashlib.sha1(link.encode()).hexdigest()[:16], "source": source,
                     "category": category, "title_en": title[:300], "url": link,
                     "published_at": published.isoformat()})
    return rows


def collect(now, *, fetcher=fetch, feeds=FEEDS):
    found = []
    for source, category, url, rule in feeds:
        try:
            found += parse_feed(fetcher(url), source, category, rule, now)
        except Exception as exc:
            print("[us-macro-news] feed_error %s %s" % (url, type(exc).__name__), flush=True)
    return found


def translate_deepl(texts, *, api_key=None, opener=urllib.request.urlopen):
    """DeepL, English -> Korean. Returns translations in the same order."""
    api_key = (api_key or os.environ.get("DEEPL_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("deepl_key_missing")
    host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
    body = urllib.parse.urlencode([("text", t) for t in texts] +
                                  [("source_lang", "EN"), ("target_lang", "KO")]).encode()
    request = urllib.request.Request(
        "https://%s/v2/translate" % host, data=body, method="POST",
        headers={"Authorization": "DeepL-Auth-Key " + api_key, "User-Agent": "gaemiGTP-news/1.0",
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with opener(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("deepl_http_%d" % exc.code) from None
    out = [str(row.get("text") or "").strip() for row in data.get("translations") or []]
    if len(out) != len(texts) or not all(out):
        raise RuntimeError("deepl_bad_response")
    return out


def translate_google(texts, *, api_key=None, opener=urllib.request.urlopen):
    """Google Cloud Translation (basic v2), English -> Korean, plain text."""
    api_key = (api_key or os.environ.get("GOOGLE_TRANSLATE_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("google_key_missing")
    body = json.dumps({"q": list(texts), "source": "en", "target": "ko", "format": "text"}).encode()
    request = urllib.request.Request(
        "https://translation.googleapis.com/language/translate/v2", data=body, method="POST",
        headers={"X-Goog-Api-Key": api_key, "User-Agent": "gaemiGTP-news/1.0",
                 "Content-Type": "application/json"})
    try:
        with opener(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("google_http_%d" % exc.code) from None
    out = [str(row.get("translatedText") or "").strip()
           for row in (data.get("data") or {}).get("translations") or []]
    if len(out) != len(texts) or not all(out):
        raise RuntimeError("google_bad_response")
    return out


def translate(texts, *, providers=(("deepl", translate_deepl), ("google", translate_google))):
    """DeepL first; Google when DeepL fails (e.g. monthly limit, HTTP 456). Returns (texts, provider)."""
    errors = []
    for name, provider in providers:
        try:
            return provider(texts), name
        except Exception as exc:
            errors.append(str(exc) or type(exc).__name__)
    raise RuntimeError("all_translators_failed:" + ",".join(errors))


def read_state(path=STATE_PATH):
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(state, path=STATE_PATH):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".macro-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False)
    os.replace(tmp, path)


def upload_json(payload, object_key, uploader=None):
    if uploader is None:
        from backend.services.r2_news_uploader import upload_file as uploader
    fd, tmp = tempfile.mkstemp(prefix="us-macro-news-", suffix=".json")
    path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        if not uploader(path, object_key=object_key):
            raise RuntimeError("r2_upload_failed")
    finally:
        path.unlink(missing_ok=True)


def run(now=None, *, collector=collect, translator=translate, upload=upload_json, state_path=STATE_PATH):
    now = now or dt.datetime.now(dt.timezone.utc)
    state = read_state(state_path)
    items = [row for row in state.get("items") or [] if isinstance(row, dict) and row.get("id")]
    known = {row["id"] for row in items}
    fresh, seen = [], set()
    for row in collector(now):
        if row["id"] not in known and row["id"] not in seen:
            seen.add(row["id"])
            fresh.append(row)
    if not fresh:
        print("[us-macro-news] no_new_items", flush=True)
        return {"status": "unchanged", "new": 0}
    try:
        korean, provider = translator([row["title_en"] for row in fresh])
    except Exception as exc:
        # Untranslated headlines are not published; they are retried next run.
        print("[us-macro-news] translate_error=" + str(exc), flush=True)
        return {"status": "translate_failed", "new": len(fresh)}
    for row, text in zip(fresh, korean):
        row["title"] = text[:200]
    items = sorted(items + fresh, key=lambda r: r["published_at"], reverse=True)[:KEEP_ITEMS]
    upload({"ok": True, "generated_at": now.isoformat(), "items": items}, OBJECT_KEY)
    state["items"] = items
    write_state(state, state_path)
    print("[us-macro-news] published new=%d total=%d chars=%d translator=%s" % (
        len(fresh), len(items), sum(len(r["title_en"]) for r in fresh), provider), flush=True)
    return {"status": "published", "new": len(fresh)}


def main():
    app_root = str(Path(__file__).resolve().parents[1])
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    try:
        run()
    except Exception as exc:
        print("[us-macro-news] failed=" + type(exc).__name__, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
