#!/usr/bin/env python3
"""Read-only, one-shot NASDAQ:NVDA TradingView Data API verification.

Maximum two external requests: one filtered news-list GET, one article-detail GET.
Uses existing server environment; no persistent writes, no worker lifecycle changes.
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

SYMBOL = "NASDAQ:NVDA"
TIMEOUT = 15


def emit(event, **values):
    print("TV_NVDA_" + event + "=" + json.dumps(values, ensure_ascii=False, default=str), flush=True)


def request_json(url, headers):
    request = urllib.request.Request(
        url, headers={**headers, "Accept": "application/json", "User-Agent": "gaemiGTP-NVDA-one-shot/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            status = response.status
            raw = response.read(700001)
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read(2000)
    except Exception as exc:
        emit("NETWORK_ERROR", error=type(exc).__name__, message=str(exc)[:220])
        return None, None
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        emit("NON_JSON", status=status, bytes=len(raw), preview=raw[:160].decode("utf-8", "replace"))
        return status, None
    if status != 200:
        error = data.get("error") if isinstance(data, dict) else None
        emit("HTTP_ERROR", status=status, error=str(error)[:380], success=data.get("success") if isinstance(data, dict) else None)
        return status, None
    return status, data


def list_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for target in (payload, payload.get("data"), payload.get("result")):
            if isinstance(target, list):
                return target
            if isinstance(target, dict):
                for key in ("items", "news", "results", "stories", "list"):
                    value = target.get(key)
                    if isinstance(value, list):
                        return value
    return []


def summary(item):
    p = item.get("provider")
    publisher = p.get("name") if isinstance(p, dict) else p
    published = item.get("published") or item.get("published_at") or item.get("date")
    if isinstance(published, (int, float)):
        published = datetime.datetime.fromtimestamp(published, datetime.timezone.utc).isoformat()
    return {
        "id": str(item.get("id") or item.get("newsId") or item.get("news_id") or "")[:200],
        "title": str(item.get("title") or item.get("headline") or "")[:350],
        "provider": str(publisher or item.get("source") or "")[:120],
        "published": published,
        "permission": item.get("permission"),
        "storyPath": str(item.get("storyPath") or "")[:300],
        "relatedSymbols": [
            s.get("symbol") for s in (item.get("relatedSymbols") or [])
            if isinstance(s, dict) and isinstance(s.get("symbol"), str)
        ][:10],
    }


def body_from(obj, depth=0):
    if depth > 4:
        return ""
    if isinstance(obj, dict):
        for key in ("body", "content", "articleBody", "article_body", "text", "articleText", "description"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, (dict, list)):
                candidate = body_from(value, depth + 1)
                if candidate:
                    return candidate
        for key in ("data", "article", "story", "news", "content"):
            value = obj.get(key)
            if isinstance(value, (dict, list)):
                candidate = body_from(value, depth + 1)
                if candidate:
                    return candidate
    if isinstance(obj, list):
        texts = [body_from(row, depth + 1) for row in obj[:30]]
        return "\n".join(t for t in texts if t)
    return ""


def main():
    key = (os.environ.get("TRADINGVIEW_DATA_API_KEY") or os.environ.get("TRADINGVIEW_API_KEY") or "").strip()
    rapid_key = (os.environ.get("TRADINGVIEW_RAPIDAPI_KEY") or os.environ.get("RAPIDAPI_KEY") or "").strip()
    if key:
        base = "https://api.tradingviewapi.com"
        headers = {"Authorization": "Bearer " + key}
        auth = "tradingview_console"
    elif rapid_key:
        base = "https://tradingview-data1.p.rapidapi.com"
        headers = {"x-rapidapi-host": "tradingview-data1.p.rapidapi.com", "x-rapidapi-key": rapid_key}
        auth = "rapidapi"
    else:
        emit("STOP", reason="api_key_not_found", expected_env_keys=[
            "TRADINGVIEW_DATA_API_KEY", "TRADINGVIEW_API_KEY", "TRADINGVIEW_RAPIDAPI_KEY", "RAPIDAPI_KEY"])
        return 2
    emit("START", symbol=SYMBOL, authentication=auth, calls_max=2)
    query = urllib.parse.urlencode({"symbol": SYMBOL, "lang": "en", "market": "stock", "market_country": "US"})
    status, data = request_json(base + "/api/news?" + query, headers)
    if status != 200 or data is None:
        emit("STOP", reason="list_request_failed", status=status)
        return 3
    items = [item for item in list_items(data) if isinstance(item, dict)]
    emit("LIST", status=status, count=len(items), top=[summary(item) for item in items[:3]],
         root_keys=list(data.keys())[:12] if isinstance(data, dict) else [])
    if not items:
        emit("STOP", reason="news_list_empty_or_unrecognized", data_keys=list(data.get("data", {}).keys())[:20] if isinstance(data, dict) and isinstance(data.get("data"), dict) else [])
        return 4
    first = items[0]
    news_id = str(first.get("id") or first.get("newsId") or first.get("news_id") or "").strip()
    if not news_id:
        emit("STOP", reason="missing_news_id", first_keys=list(first.keys())[:20])
        return 5
    url = base + "/api/news/" + urllib.parse.quote(news_id, safe="")
    detail_status, detail = request_json(url, headers)
    if detail_status != 200 or detail is None:
        emit("DETAIL", status=detail_status, id=news_id[:200], available=False)
        return 6
    raw_body = body_from(detail)
    plain = html.unescape(re.sub(r"<[^>]*>", " ", raw_body))
    plain = re.sub(r"\s+", " ", plain).strip()
    block = detail.get("data", detail) if isinstance(detail, dict) else detail
    if isinstance(block, dict):
        detail_summary = {
            "title": str(block.get("title") or block.get("headline") or "")[:350],
            "keys": list(block.keys())[:28],
            "provider": str(block.get("provider") or block.get("source") or "")[:150],
            "link": str(block.get("url") or block.get("storyPath") or "")[:350],
        }
    else:
        detail_summary = {"type": type(block).__name__}
    emit("DETAIL", status=detail_status, id=news_id[:200],
         body_present=bool(plain), body_characters=len(plain), body_excerpt=plain[:320],
         detail=detail_summary)
    emit("DONE", calls=2, succeeded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
