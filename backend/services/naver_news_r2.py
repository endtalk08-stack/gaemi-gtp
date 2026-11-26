"""Publish the Naver raw-news feed into the unified Cloudflare R2 snapshot.

This module deliberately does not call AI or change the Naver API adapter. The
caller supplies the query set; this module normalizes and safely merges the
result into news/latest.json so other existing news sources are preserved.
"""
from __future__ import annotations

import datetime as dt
import json
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


OPTIONAL_LIST_FIELDS = (
    "news_sections",
    "event_matches",
    "market_event_matches",
    "symbols",
)
OPTIONAL_OBJECT_FIELDS = ("event_category", "market_event_category")
OPTIONAL_TEXT_FIELDS = ("body", "list_excerpt", "news_section")


def _valid_url(value: object) -> str:
    url = str(value or "").strip()
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return url


def _normalise_item(row: object) -> dict | None:
    if not isinstance(row, dict):
        return None
    title = str(row.get("title") or "").strip()
    url = _valid_url(row.get("url") or row.get("link") or row.get("originallink"))
    if not title or not url:
        return None

    description = str(row.get("summary") or row.get("description") or "").strip()
    item = {
        "title": title,
        "source": str(row.get("source") or "네이버 뉴스").strip(),
        "summary": description,
        "published_at": str(row.get("published_at") or row.get("pubDate") or "").strip(),
        "url": url,
    }
    # Do not turn a Naver description into a fabricated full article body.
    for key in OPTIONAL_TEXT_FIELDS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            item[key] = value.strip()
    for key in OPTIONAL_LIST_FIELDS:
        value = row.get(key)
        if isinstance(value, list):
            item[key] = value
    for key in OPTIONAL_OBJECT_FIELDS:
        value = row.get(key)
        if isinstance(value, dict):
            item[key] = value
    if row.get("category"):
        item["category"] = str(row["category"])
    return item


def _sort_timestamp(item: dict) -> float:
    value = str(item.get("published_at") or "").strip()
    if not value:
        return 0.0
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _merge_items(existing: list, incoming: list) -> list[dict]:
    merged = []
    seen = set()
    # New Naver records take precedence over older copies of the same article.
    for row in list(incoming) + list(existing):
        if not isinstance(row, dict):
            continue
        item = dict(row)
        url = _valid_url(item.get("url") or item.get("link"))
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        key = url.lower() or title.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    merged.sort(key=_sort_timestamp, reverse=True)
    return merged


def build_naver_snapshot(rows: list, *, existing_snapshot: dict | None = None,
                         generated_at: str | None = None) -> dict:
    incoming = []
    seen = set()
    for row in rows if isinstance(rows, list) else []:
        item = _normalise_item(row)
        if item is None:
            continue
        key = item["url"].lower()
        if key not in seen:
            seen.add(key)
            incoming.append(item)
    if not incoming:
        raise ValueError("no_publishable_naver_news; preserve_previous_r2_snapshot")

    existing_items = []
    if existing_snapshot is not None:
        if (not isinstance(existing_snapshot, dict)
                or existing_snapshot.get("ok") is not True
                or not isinstance(existing_snapshot.get("items"), list)):
            raise ValueError("invalid_existing_news_snapshot; preserve_previous_r2_snapshot")
        existing_items = existing_snapshot["items"]

    items = _merge_items(existing_items, incoming)
    timestamp = generated_at or dt.datetime.now(dt.timezone.utc).isoformat()
    return {
        "ok": True,
        "source": "unified_news_feed",
        "generated_at": timestamp,
        "count": len(items),
        "items": items,
    }


def publish_naver_news(rows: list) -> dict:
    """Merge Naver records with the current unified feed, then upload once."""
    from backend.services.r2_news_uploader import (
        read_latest_news_snapshot,
        upload_file,
    )

    previous = read_latest_news_snapshot()
    snapshot = build_naver_snapshot(rows, existing_snapshot=previous)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(snapshot, handle, ensure_ascii=False, separators=(",", ":"))
        if not upload_file(temp_path, object_key="news/latest.json"):
            raise RuntimeError("r2_latest_news_upload_failed; previous_snapshot_preserved")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return snapshot


def collect_and_publish_naver_news(queries: list[str], *, section: str = "market",
                                   limit: int = 200, per_query: int = 20) -> dict:
    """Collect Naver-only market news for caller-supplied queries and publish it."""
    from backend.services.news_feed import fetch_naver_news

    rows = fetch_naver_news(
        queries,
        limit=limit,
        per_query=per_query,
        section=section,
        raise_on_error=True,
    )
    return publish_naver_news(rows)
