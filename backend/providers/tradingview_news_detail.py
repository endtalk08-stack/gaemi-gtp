"""Optional, budget-capped TradingView Data API article-detail enrichment.

Uses the IDs already returned by the US news bundle (no additional list request).
No network call unless enrich_articles() is explicitly given a positive max_requests.
The API's detail response fields can differ by provider; never fabricate text.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

DETAIL_BASE_URL = "https://api.tradingviewapi.com/api/news/"
MAX_PER_RUN = 10
MAX_DETAIL_CHARS = 100_000
MAX_FIELD_CHARS = 10_000


def _text(value):
    return " ".join(value.split()).strip() if isinstance(value, str) else ""


def _detail_id(article):
    value = article.get("id") or article.get("newsId")
    if value is None:
        return ""
    value = str(value).strip()
    return value if value and len(value) <= 300 else ""


def _get_detail(news_id, key, opener):
    url = DETAIL_BASE_URL + urllib.parse.quote(news_id, safe="")
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + key,
        "Accept": "application/json",
        "User-Agent": "gaemiGTP-news-worker/1.0",
    })
    with opener(request, timeout=10) as response:
        payload = json.loads(response.read(200_000).decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("invalid_news_detail_response")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("missing_news_detail_data")
    return data


def _candidate_objects(data):
    """Find known wrappers without assuming one fixed provider response shape."""
    yield data
    for key in ("item", "news", "story", "article"):
        value = data.get(key)
        if isinstance(value, dict):
            yield value


def _read_string(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "plainText", "html", "content", "value"):
            if isinstance(value.get(key), str):
                return value[key].strip()
    if isinstance(value, list):
        parts = [_read_string(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    return ""


def _first_field(data, fields, limit):
    for obj in _candidate_objects(data):
        for field in fields:
            value = _read_string(obj.get(field))
            if value:
                return value[:limit]
    return ""


def _extract_detail(data):
    return {
        "detail_body": _first_field(data, (
            "body", "articleBody", "article_body", "bodyText",
            "fullText", "full_text", "content", "text", "storyText",
        ), MAX_DETAIL_CHARS),
        "detail_description": _first_field(data, (
            "shortDescription", "short_description", "description", "excerpt",
        ), MAX_FIELD_CHARS),
        "detail_summary": _first_field(data, (
            "summary", "shortSummary", "short_summary", "abstract",
        ), MAX_FIELD_CHARS),
    }


def enrich_articles(items, *, max_requests=0, opener=None, api_key=None):
    """Return (new_items, stats). Positive budget is required for API calls.

    Details are fetched only once for IDs missing body, description or summary.
    A 429 stops the run instead of retrying, to prevent overspending.
    Raw article bodies remain in the short-lived private worker cache; publication requires separate rights approval.
    Headline-only articles are not enriched into publicly displayed summaries.
    """
    budget = max(0, min(int(max_requests), MAX_PER_RUN))
    key = (api_key if api_key is not None else os.getenv("TRADINGVIEW_API_KEY", "")).strip()
    opener = opener or urllib.request.urlopen
    rows = [dict(item) for item in items if isinstance(item, dict)]
    stats = {"requested": 0, "bodies": 0, "described": 0, "summarized": 0, "blocked": 0, "failed": 0, "skipped": 0}
    if not budget or not key:
        stats["skipped"] = len(rows)
        return rows, stats
    done = set()
    halted = False
    for row in rows:
        article_id = _detail_id(row)
        if (halted or stats["requested"] >= budget or not article_id
                or article_id in done or row.get("detail_checked")):
            stats["skipped"] += 1
            continue
        # Never republish an article body when upstream rights say headline-only.
        if row.get("permission") == "headline":
            stats["blocked"] += 1
            row["detail_checked"] = "headline_only"
            continue
        done.add(article_id)
        stats["requested"] += 1
        try:
            data = _get_detail(article_id, key, opener)
            values = _extract_detail(data)
            # A provider's detail-level restriction takes precedence.
            detail_permission = next((
                item.get("permission") for item in _candidate_objects(data)
                if item.get("permission") is not None
            ), None)
            if detail_permission is not None:
                row["detail_permission"] = detail_permission
            if detail_permission == "headline":
                row["detail_checked"] = "headline_only"
                stats["blocked"] += 1
                continue
            for field, metric in (
                ("detail_body", "bodies"),
                ("detail_description", "described"),
                ("detail_summary", "summarized"),
            ):
                if values[field]:
                    row[field] = values[field]
                    stats[metric] += 1
            if values["detail_description"] and not row.get("shortDescription"):
                row["shortDescription"] = values["detail_description"]
            row["detail_checked"] = "content" if any(values.values()) else "no_content"
        except urllib.error.HTTPError as exc:
            stats["failed"] += 1
            if exc.code in (401, 402, 403, 429):
                halted = True
        except (ValueError, TypeError, UnicodeError, OSError):
            stats["failed"] += 1
    return rows, stats
