#!/usr/bin/env python3
"""Clear only cached TradingView article items; preserve monthly usage counters."""
import fcntl
import json
from pathlib import Path

CACHE = Path("/var/lib/gaemigtp-news/tradingview-us-stock-news.json")
if CACHE.is_symlink() or not CACHE.is_file():
    raise SystemExit("TradingView cache file missing or unsafe")
lock_path = CACHE.with_suffix(".lock")
if lock_path.is_symlink():
    raise SystemExit("TradingView cache lock unsafe")
with lock_path.open("a+", encoding="utf-8") as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    state = json.loads(CACHE.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or not isinstance(state.get("items"), list):
        raise SystemExit("TradingView cache format invalid; nothing changed")
    old_count = len(state["items"])
    state["items"] = []
    # Preserve month, requests and last_attempt to avoid resetting API usage limits.
    import tempfile, os
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(CACHE.parent), prefix=".tv-clear-", delete=False) as f:
            name = f.name
            os.fchmod(f.fileno(), 0o600)
            json.dump(state, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, CACHE)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
print(json.dumps({"result":"cleared","deleted_article_count":old_count,"cache_file_retained":True,"monthly_request_counter_preserved":True},ensure_ascii=False))
