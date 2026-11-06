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
MAX_DETAIL_CHARS = 10_000


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


def _extract_description(data):
    """Only explicit description/summary fields, never a substring of HTML body."""
    candidates = [data]
    for key in ("item", "news", "story", "article"):
        if isinstance(data.get(key), dict):
            candidates.append(data[key])
    for row in candidates:
        for field in ("shortDescription", "short_description", "description", "summary", "excerpt"):
            description = _text(row.get(field))
            if description:
                return description[:MAX_DETAIL_CHARS]
    return ""


def enrich_articles(items, *, max_requests=0, opener=None, api_key=None):
    """Return (new_items, stats). Positive budget is required for API calls.

    Details are fetched only for previously unseen IDs missing a description.
    A 429 stops the run instead of retrying, to prevent overspending.
    Raw article bodies are not published or retained.
    Headline-only articles are not enriched into publicly displayed summaries.
    """
    budget = max(0, min(int(max_requests), MAX_PER_RUN))
    key = (api_key if api_key is not None else os.getenv("TRADINGVIEW_API_KEY", "")).strip()
    opener = opener or urllib.request.urlopen
    rows = [dict(item) for item in items if isinstance(item, dict)]
    stats = {"requested": 0, "described": 0, "blocked": 0, "failed": 0, "skipped": 0}
    if not budget or not key:
        stats["skipped"] = len(rows)
        return rows, stats
    done = set()
    halted = False
    for row in rows:
        article_id = _detail_id(row)
        if (halted or stats["requested"] >= budget or not article_id
                or article_id in done or row.get("shortDescription")
                or row.get("short_description") or row.get("detail_checked")):
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
            description = _extract_description(data)
            # Check any detail-level permission too.
            detail_permission = data.get("permission")
            if detail_permission == "headline":
                row["detail_checked"] = "headline_only"
                stats["blocked"] += 1
                continue
            if description:
                row["shortDescription"] = description
                row["detail_checked"] = "description"
                stats["described"] += 1
            else:
                row["detail_checked"] = "no_description"
        except urllib.error.HTTPError as exc:
            stats["failed"] += 1
            if exc.code in (401, 402, 403, 429):
                halted = True
        except (ValueError, TypeError, UnicodeError, OSError):
            stats["failed"] += 1
    return rows, stats
