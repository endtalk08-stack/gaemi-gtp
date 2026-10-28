"""Isolated NVDA-only Alpaca news collection test: one GET, local JSON only.
No DB, AI, alerts, trading or existing news worker operations.
"""
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

DEST = pathlib.Path("/run/gaemi-gateway/nvda-news-test-20261028.json")


def fail(reason, status=2):
    print("NVDA_NEWS_TEST_ERROR=" + reason, flush=True)
    return status


def main():
    state = subprocess.run(
        ["systemctl", "is-active", "gaemigtp-news.service"],
        capture_output=True, text=True, timeout=5, check=False
    ).stdout.strip()
    if state != "inactive":
        return fail("news_worker_not_paused")
    key = os.environ.get("APCA_API_KEY_ID", "").strip()
    secret = os.environ.get("APCA_API_SECRET_KEY", "").strip()
    if not key or not secret:
        return fail("alpaca_credentials_missing")
    if not DEST.parent.is_dir() or DEST.exists():
        return fail("local_output_not_safe_or_already_exists")

    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(hours=24)
    params = urllib.parse.urlencode({
        "symbols": "NVDA",
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": end.isoformat().replace("+00:00", "Z"),
        "sort": "desc",
        "limit": 20,
        "include_content": "true",
    })
    request = urllib.request.Request(
        "https://data.alpaca.markets/v1beta1/news?" + params,
        headers={
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json",
            "User-Agent": "gaemi-nvda-isolated-news-check/1.0",
        }, method="GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=18) as response:
            raw = response.read(2000001)
        if len(raw) > 2000000:
            return fail("api_response_too_large")
        payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        return fail("alpaca_http_" + str(int(exc.code)))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return fail("alpaca_transport_or_json")
    if not isinstance(payload, dict) or not isinstance(payload.get("news"), list):
        return fail("unexpected_api_payload")
    news = payload["news"]
    seen = set()
    collected = []
    unmatched = duplicates = 0
    for item in news:
        if not isinstance(item, dict):
            continue
        symbols = item.get("symbols")
        if not isinstance(symbols, list) or "NVDA" not in symbols:
            unmatched += 1
            continue
        headline = str(item.get("headline") or "").strip()
        url = str(item.get("url") or "").strip()
        keys = [
            "id:" + str(item["id"]) if item.get("id") is not None else "",
            "url:" + url.lower() if url else "",
            "title:" + re.sub(r"\s+", " ", headline).casefold() if headline else "",
        ]
        keys = [k for k in keys if k]
        if not keys:
            continue
        if any(k in seen for k in keys):
            duplicates += 1
            continue
        seen.update(keys)
        collected.append({
            "id": item.get("id"),
            "headline": headline,
            "source": item.get("source"),
            "url": url,
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "symbols": symbols,
            "summary": item.get("summary") or "",
            "content": item.get("content") or "",
        })
    latest_state = subprocess.run(
        ["systemctl", "is-active", "gaemigtp-news.service"],
        capture_output=True, text=True, timeout=5, check=False
    ).stdout.strip()
    if latest_state != "inactive":
        return fail("news_worker_changed")
    result = {
        "test": "NVDA Alpaca news isolated GET",
        "window_start_utc": start.isoformat(),
        "window_end_utc": end.isoformat(),
        "symbol": "NVDA",
        "api_requests": 1,
        "raw_count": len(news),
        "stock_mismatch_count": unmatched,
        "duplicate_count": duplicates,
        "unique_count": len(collected),
        "articles_with_content": sum(bool(str(x["content"]).strip()) for x in collected),
        "news_worker": latest_state,
        "db_calls": 0,
        "ai_calls": 0,
        "articles": collected,
    }
    try:
        fd = os.open(str(DEST), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(result, out, ensure_ascii=False, indent=2)
    except OSError:
        return fail("local_json_save_failed")
    summary = {k: v for k, v in result.items() if k not in ("articles",)}
    summary["json_path"] = str(DEST)
    print("NVDA_NEWS_TEST_RESULT=" + json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    for index, item in enumerate(collected[:5], 1):
        print("NVDA_NEWS_SAMPLE_" + str(index) + "=" + json.dumps({
            "headline": item["headline"][:180],
            "source": item["source"],
            "created_at": item["created_at"],
        }, ensure_ascii=False), flush=True)
    print("NVDA_NEWS_TEST_PASS_LOCAL_JSON_ONLY", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
