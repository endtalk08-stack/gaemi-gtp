"""Official company-news feeds for selected US stocks.

This provider only collects source records. Business ranking stays in news_feed/scoring.
Only feeds with a stable public RSS/Atom endpoint are registered here; unsupported
stocks simply return no official-feed rows and continue to use SEC/NAVER sources.
"""

import datetime
import html
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime


REQUEST_TIMEOUT = 2.2
_CACHE_TTL = 180
_CACHE = {}
_CACHE_LOCK = threading.Lock()

OFFICIAL_FEEDS = {
    "알파벳": [
        ("Google Blog", "https://blog.google/rss/"),
        ("Google Cloud Blog", "https://cloudblog.withgoogle.com/rss"),
    ],
    "애플": [
        ("Apple Newsroom", "https://www.apple.com/newsroom/rss-feed.rss"),
    ],
    "엔비디아": [
        ("NVIDIA Blog", "https://blogs.nvidia.com/feed/"),
    ],
    "마이크로소프트": [
        ("Microsoft Blog", "https://blogs.microsoft.com/feed/"),
    ],
    "아마존": [
        ("AWS News Blog", "https://aws.amazon.com/blogs/aws/feed/"),
    ],
    "메타": [
        ("Meta Newsroom", "https://about.fb.com/news/feed/"),
    ],
}


def _clean_text(value):
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
    except Exception:
        try:
            dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).isoformat()


def _local_name(tag):
    return str(tag or "").rsplit("}", 1)[-1].lower()


def _first_child_text(node, names):
    names = {name.lower() for name in names}
    for child in list(node):
        if _local_name(child.tag) in names:
            return "".join(child.itertext()).strip()
    return ""


def _entry_link(node):
    for child in list(node):
        if _local_name(child.tag) != "link":
            continue
        href = str(child.attrib.get("href") or "").strip()
        rel = str(child.attrib.get("rel") or "alternate").strip().lower()
        if href and rel in ("", "alternate"):
            return href
        if not href:
            text = "".join(child.itertext()).strip()
            if text:
                return text
    return ""


def _parse_feed_bytes(payload, *, stock_name, source_name, feed_url):
    """Parse RSS or Atom bytes into normalized shared-news rows."""
    try:
        root = ET.fromstring(payload)
    except Exception:
        return []

    entries = [
        node for node in root.iter()
        if _local_name(node.tag) in {"item", "entry"}
    ]
    rows = []
    for entry in entries:
        title = _clean_text(_first_child_text(entry, {"title"}))
        if not title:
            continue
        description = _clean_text(_first_child_text(entry, {"description", "summary", "content"}))
        published_at = _parse_date(_first_child_text(entry, {"pubdate", "published", "updated", "date"}))
        link = _entry_link(entry)
        if not link:
            link = feed_url
        rows.append({
            "provider": "official_feed",
            "source_type": "official_company",
            "provider_stock": stock_name,
            "source": source_name,
            "source_quality": 100,
            "title": title,
            "description": description,
            "summary": description,
            "published_at": published_at,
            "link": link,
            "url": link,
            "category": "종목",
            "region": "미국",
        })
    return rows


def _fetch_feed(stock_name, source_name, feed_url):
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(feed_url)
        if cached and now - cached[0] <= _CACHE_TTL:
            return list(cached[1])

    request = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "gaemiGTP/1.0",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = response.read()
        rows = _parse_feed_bytes(
            payload,
            stock_name=stock_name,
            source_name=source_name,
            feed_url=feed_url,
        )
    except Exception as exc:
        print(
            f"[provider:official-news] failed stock={stock_name} source={source_name}: "
            f"{type(exc).__name__}: {exc}"
        )
        rows = []

    with _CACHE_LOCK:
        _CACHE[feed_url] = (now, list(rows))
    return rows


def fetch_company_news(stock_name, limit=12):
    feeds = list(OFFICIAL_FEEDS.get(str(stock_name or "").strip(), []))
    if not feeds:
        return []

    rows = []
    with ThreadPoolExecutor(max_workers=min(3, len(feeds))) as pool:
        futures = {
            pool.submit(_fetch_feed, stock_name, source_name, feed_url): (source_name, feed_url)
            for source_name, feed_url in feeds
        }
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except Exception:
                continue

    seen = set()
    deduped = []
    for row in sorted(rows, key=lambda item: item.get("published_at") or "", reverse=True):
        key = row.get("url") or row.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= max(1, int(limit)):
            break
    return deduped
