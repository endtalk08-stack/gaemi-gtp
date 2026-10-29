"""DigitalOcean stock-news worker: US trading-value and popular TOP20; Naver US news restored.

No fixed-stock priority or domestic collection. Reuse existing Naver news, company feeds, and SEC.
Keeps the existing once-per-US-exchange-day Groq scheduling and Neon storage.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

from backend.services import news_feed
from backend.services.news_result import build_stock_news_result
from backend.services import news_processed_store as store

RESULT_LIMIT = 50
STORYBOARD_LIMIT = 3
TIMEZONE = "Asia/Seoul"

# Existing public ranking API is read-only. No new tickers are registered.
# Use the US trading-value TOP20 only; process at most one stock per cycle.
RANKING_ENDPOINTS = (
    ("미국", "market=us", "/market/trading-value"),
)
# One ticker each worker tick; current 20-symbol ranking frozen for full round.



# Rotation progress is local metadata (not article data and not Neon).
# /var/tmp survives ordinary service restarts; each write is atomic and mode 0600.
ROTATION_STATE_PATH = "/var/lib/gaemigtp-news/rotation.json"

def _read_rotation_state():
    from pathlib import Path
    path = Path(ROTATION_STATE_PATH)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("invalid_rotating_state_file")
    return value

def _write_rotation_state(state):
    import tempfile
    from pathlib import Path
    path = Path(ROTATION_STATE_PATH)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(path.parent),
            prefix=".gaemigtp-rotation-", delete=False,
        ) as handle:
            name = handle.name
            os.fchmod(handle.fileno(), 0o600)
            json.dump(state, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)

def read_ranked_stocks(market, query, path, *, snapshot_path=None):
    """Use Kiwoom's existing local snapshot; never request Render or Neon."""
    if market != "미국" or query != "market=us" or path != "/market/trading-value":
        return []
    from pathlib import Path
    from backend.services.us_top20_rotation import normalize_ranking
    file=Path(snapshot_path) if snapshot_path is not None else Path(
        "/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
    if file.is_symlink():
        raise ValueError("unsafe_local_ranking_path")
    data=json.loads(file.read_text(encoding="utf-8"))
    if (not isinstance(data,dict) or data.get("schema_version") != 1
            or data.get("source") != "kiwoom" or data.get("market") != "US"
            or data.get("rank_type") != "trading_value"):
        raise ValueError("invalid_local_kiwoom_snapshot")
    return normalize_ranking(data.get("items"))


def next_ranked_stock(state):
    from backend.services.us_top20_rotation import plan_tick, RankingUnavailable
    # Fetch a new top-20 ranking only when a new 20-stock cycle starts.
    # If ranking lookup fails, reuse the last complete frozen cycle (not a partial one).
    ranked_rows = []
    if not state.get("cycle") or state.get("next_index", 20) >= 20:
        market, query, path = RANKING_ENDPOINTS[0]
        try:
            ranked_rows = read_ranked_stocks(market, query, path)
            print(f"[news-worker] ranking market={market} matches={len(ranked_rows)}", flush=True)
        except Exception as exc:
            print(f"[news-worker] ranking_error={type(exc).__name__}", flush=True)
    try:
        item, new_state = plan_tick(state, ranked_rows)
    except RankingUnavailable:
        print("[news-worker] top20 ranking unavailable; no stock skipped", flush=True)
        return None
    state.clear()
    state.update(new_state)
    # Save pending cursor BEFORE doing provider/API work.
    _write_rotation_state(state)
    return "미국", item["name"], item["symbol"]

def process_stock(market, stock_name):
    if market != "미국":
        return "skipped_non_us"
    params = dict(market=market, limit=RESULT_LIMIT,
                  storyboard_limit=STORYBOARD_LIMIT, display_timezone=TIMEZONE)
    raw = news_feed.fetch_stock_news(stock_name, market=market, limit=RESULT_LIMIT, raise_on_error=True)
    if not raw:
        raise RuntimeError("empty news source; keep previous known-good snapshot")
    fingerprint = store.source_fingerprint(raw)
    if store.read_signature(stock_name, **params) == fingerprint:
        try:
            import sys
            from pathlib import Path
            ops_dir = str(Path(__file__).resolve().parents[1] / "ops")
            if ops_dir not in sys.path:
                sys.path.insert(0, ops_dir)
            from staged_ai_sequential_batch import apply_unchanged_worker_ai
            apply_unchanged_worker_ai(store=store, market=market, stock_name=stock_name,
                                      raw=raw, fingerprint=fingerprint, params=params)
        except Exception as ai_exc:
            print(f"[news-ai] stock={stock_name} error={type(ai_exc).__name__}", flush=True)
        store.mark_checked(stock_name, **params)
        return "unchanged"
    result = build_stock_news_result(stock_name, raw_news_list=raw, **params)
    if result.get("_news_status") != "ok":
        raise RuntimeError("analysis failed; previous good result preserved")
    store.save_snapshot(stock_name, fingerprint=fingerprint, result=result, **params)
    try:
        import sys
        from pathlib import Path
        ops_dir = str(Path(__file__).resolve().parents[1] / "ops")
        if ops_dir not in sys.path:
            sys.path.insert(0, ops_dir)
        from staged_ai_sequential_batch import apply_worker_ai
        apply_worker_ai(store=store, market=market, stock_name=stock_name,
                        raw=raw, fingerprint=fingerprint, result=result, params=params)
    except Exception as ai_exc:
        print(f"[news-ai] stock={stock_name} error={type(ai_exc).__name__}", flush=True)
    return "updated"

def run_once(state, *, maintenance=True):
    target = next_ranked_stock(state)
    if target is not None:
        from backend.services.us_top20_rotation import finish_tick
        market, stock_name, symbol = target
        ok = False
        try:
            result = process_stock(market, stock_name)
            ok = True
            print(f"[news-worker] market={market} stock={stock_name} {result}", flush=True)
        except Exception as exc:
            print(f"[news-worker] market={market} stock={stock_name} error={type(exc).__name__}", flush=True)
        finally:
            new_state = finish_tick(state, symbol, ok=ok)
            _write_rotation_state(new_state)
            state.clear()
            state.update(new_state)
    if not maintenance:
        return target is not None
    try:
        import sys
        from pathlib import Path
        ops_dir = str(Path(__file__).resolve().parents[1] / "ops")
        if ops_dir not in sys.path:
            sys.path.insert(0, ops_dir)
        from staged_auto_ai_daily import process_due_ai_snapshots
        ai_count = process_due_ai_snapshots()
        if ai_count:
            print("[news-ai] scheduled processed=%s" % ai_count, flush=True)
    except Exception as ai_exc:
        print("[news-ai] scheduled error=%s" % type(ai_exc).__name__, flush=True)
    try:
        store.purge_expired()
    except Exception as exc:
        print(f"[news-worker] cleanup_error={type(exc).__name__}", flush=True)

    try:
        deleted = store.purge_expired_original_news()
        print(f"[news-worker] original_news_expired_deleted={deleted}", flush=True)
    except Exception as exc:
        print(f"[news-worker] original_news_cleanup_error={type(exc).__name__}", flush=True)

    return target is not None

def _news_slot(now=None):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    local=datetime.now(ZoneInfo("Asia/Seoul")) if now is None else now.astimezone(ZoneInfo("Asia/Seoul"))
    if local.hour in (1,4,7,10,13,16,19,22) and local.minute < 15:
        return local.strftime("%Y%m%d%H")
    return None

def _batch(state, now=None, *, runner=None, persist=None, sleeper=None):
    slot=_news_slot(now)
    if slot is None: return 0
    runner=runner or run_once
    persist=persist or _write_rotation_state
    sleeper=sleeper or time.sleep
    if state.get("_batch_slot") != slot:
        state["_batch_slot"]=slot
        state["_batch_progress"]=0
        persist(state)
    count=state.get("_batch_progress")
    if type(count) is not int or not 0 <= count <= 20:
        raise ValueError("invalid_batch_progress")
    attempted=0
    for i in range(count,20):
        try:
            has_stock=runner(state,maintenance=(i==19))
        except Exception:
            state["_batch_progress"]=20
            persist(state)
            raise
        state["_batch_progress"]=i+1
        persist(state)
        if not has_stock:
            state["_batch_progress"]=20
            persist(state)
            print("[news-worker] batch_stopped_no_ranking",flush=True)
            break
        attempted+=1
        if i<19: sleeper(10)
    return attempted

def main():
    os.environ["GAEMIGTP_NEWS_WORKER"]="1"
    if not store.database_url():
        raise SystemExit("NEWS_DATABASE_URL is required")
    state=_read_rotation_state()
    print("[news-worker] scheduled kst=01,04,07,10,13,16,19,22 batch=20",flush=True)
    while True:
        try:
            _batch(state)
        except Exception as exc:
            print("[news-worker] batch_error="+type(exc).__name__,flush=True)
        time.sleep(20)

if __name__ == "__main__":
    main()
