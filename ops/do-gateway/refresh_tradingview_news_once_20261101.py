#!/usr/bin/env python3
"""Clear cached TradingView stock-news items and fetch one fresh Korean response."""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import sys
import time

APP = Path("/opt/gaemigtp-news/app")
ENV_FILE = Path("/etc/gaemigtp/tradingview.env")
CACHE = Path("/var/lib/gaemigtp-news/tradingview-us-stock-news.json")
sys.path.insert(0, str(APP))

def load_key():
    if ENV_FILE.is_symlink() or not ENV_FILE.is_file():
        raise RuntimeError("tradingview_env_file_unavailable")
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("TRADINGVIEW_API_KEY="):
            value = line.split("=", 1)[1].strip().strip("\"").strip("'")
            if value:
                return value
    raise RuntimeError("tradingview_api_key_missing")

def main():
    import backend.providers.tradingview_news as tv
    now = time.time()
    month = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m")
    key = load_key()
    if not CACHE.parent.is_dir() or CACHE.parent.is_symlink() or CACHE.is_symlink():
        raise RuntimeError("unsafe_or_missing_cache_directory")
    lock_path = CACHE.with_suffix(".lock")
    if lock_path.is_symlink():
        raise RuntimeError("unsafe_cache_lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if CACHE.exists():
            state = json.loads(CACHE.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                raise RuntimeError("invalid_cache_state")
        else:
            state = {"month": month, "requests": 0, "last_attempt": 0, "items": []}
        if state.get("month") != month:
            state = {"month": month, "requests": 0, "last_attempt": 0, "items": []}
        requests = int(state.get("requests", 0))
        if requests >= tv.MONTHLY_REQUEST_LIMIT:
            raise RuntimeError("monthly_request_limit_reached; cache_not_cleared")
        old_count = len(state.get("items", [])) if isinstance(state.get("items", []), list) else -1
        # Clear old articles but preserve the monthly request counter.
        state["items"] = []
        state["last_attempt"] = 0
        tv._write_state(CACHE, state)
    fresh = tv._load_news(key)
    # Read back only counts and Nvidia-related headlines; never print credentials.
    state = json.loads(CACHE.read_text(encoding="utf-8"))
    items = state.get("items", [])
    nv = []
    for article in items:
        rel = article.get("relatedSymbols") or []
        symbols = {str(x.get("symbol") or "").upper().rsplit(":", 1)[-1]
                   for x in rel if isinstance(x, dict)}
        if "NVDA" in symbols:
            nv.append({
                "title": article.get("title", ""),
                "provider": article.get("provider"),
                "published": article.get("published"),
                "has_short_description": bool(article.get("shortDescription") or article.get("short_description")),
                "has_detail": bool(article.get("astDescription") or article.get("ast_description")),
                "has_permission": "permission" in article,
                "has_paywall": "paywall" in article,
                "has_copyright": "copyright" in article,
                "related_symbols": rel,
            })
    print(json.dumps({
        "result": "success" if items else "empty_or_failed",
        "old_cached_article_count": old_count,
        "fresh_article_count": len(items),
        "nvidia_article_count": len(nv),
        "nvidia_articles": nv[:10],
        "monthly_request_count": state.get("requests"),
        "request_language": "ko",
        "service_started": False,
    }, ensure_ascii=False))
    if not items:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
