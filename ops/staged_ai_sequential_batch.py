"""Sequential per-stock AI batch, staged only; not wired to production.

Uses existing Neon connection and reserves before any paid Groq request.
"""
import hashlib
import json
from staged_daily_groq_issues import analyze_news
from staged_ai_issue_store import save_ai_issues
from staged_daily_call_guard import reserve_once, finish_reservation


def run_stock_batch(conn, stocks, *, analyze=analyze_news, save=save_ai_issues,
                    reserve=reserve_once, finish=finish_reservation):
    """Process stocks sequentially with one durable reservation per stock/day.

    Caller supplies scheduled stock inputs and existing Neon connection.
    Reservations are committed before AI calls, even if the call later fails.
    """
    results = []
    for stock in stocks:
        market, symbol = stock["market"], stock["symbol"]
        day = stock["exchange_day"]
        articles = stock.get("articles") or []
        if not articles:
            results.append({"market": market, "symbol": symbol, "status": "no_articles",
                            "issue_count": 0, "ids": []})
            continue
        request_hash = hashlib.sha256(json.dumps(
            {"name": stock["name"], "articles": articles}, ensure_ascii=False,
            sort_keys=True, default=str).encode("utf-8")).hexdigest()
        reserved = False
        try:
            with conn.transaction():
                reserved = reserve(conn, market=market, symbol=symbol,
                                   exchange_day=day, request_hash=request_hash)
            if not reserved:
                results.append({"market": market, "symbol": symbol,
                                "status": "already_reserved", "issue_count": 0, "ids": []})
                continue
            issues = analyze(stock["name"], articles)
            ids = save(conn, issues, market=market, symbol=symbol,
                       exchange_day=day) if issues else []
            with conn.transaction():
                finish(conn, market=market, symbol=symbol, exchange_day=day,
                       request_hash=request_hash, status="completed",
                       result={"issue_ids": ids, "issue_count": len(issues)})
            results.append({"market": market, "symbol": symbol, "status": "ok",
                            "issue_count": len(issues), "ids": ids})
        except Exception as exc:
            if reserved:
                try:
                    with conn.transaction():
                        finish(conn, market=market, symbol=symbol, exchange_day=day,
                               request_hash=request_hash, status="failed",
                               failure_category=type(exc).__name__)
                except Exception:
                    pass
            results.append({"market": market, "symbol": symbol, "status": "error",
                            "error_type": type(exc).__name__})
    return results


def _worker_database_url(store):
    """Use the worker's configured Neon URL without assuming a store method."""
    import os
    value = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if value:
        return value
    getter = getattr(store, "database_url", None)
    if callable(getter):
        return getter()
    raise RuntimeError("NEWS_DATABASE_URL is not configured for AI worker")

def apply_worker_ai(*, store, market, stock_name, raw, fingerprint, result, params):
    """Run at most one AI analysis per stock/day after original snapshot is saved."""
    import os
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from staged_daily_issue_schedule import scheduled_kst_time
    if market not in ("미국", "US"):
        return
    market_code = "US"
    if not os.environ.get("GROQ_API_KEY", "").strip():
        from pathlib import Path
        key_file = Path(__file__).with_name(".groq_api_key")
        try:
            key = key_file.read_text().strip()
        except (OSError, UnicodeError):
            key = ""
        if key:
            os.environ["GROQ_API_KEY"] = key
        else:
            print("[news-ai] skipped reason=missing_groq_key", flush=True)
            return
    # Frozen to the 21 US stocks verified in Neon; no automatic expansion.
    approved_us = {"TSMC ADR","네비우스 그룹","마이크로소프트","마이크론 테크놀로지","메타","모더나","브로드컴","샌디스크","스페이스X","아마존닷컴","아이렌","아이온큐","알파벳 Class A","애플","엔비디아","오라클","인텔","일라이 릴리","코어위브","테슬라","팔란티어 테크놀로지스"}
    if stock_name not in approved_us:
        print("[news-ai] skipped reason=outside_approved_21 stock=%s" % stock_name, flush=True)
        return
    if not isinstance(result, dict) or not result.get("issue_briefs"):
        print("[news-ai] skipped reason=no_selected_issue stock=%s" % stock_name, flush=True)
        return
    from staged_ai_snapshot_integration import with_ai_issue_briefs
    from staged_daily_groq_issues import MODEL
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    us_now = now.astimezone(ZoneInfo("America/New_York"))
    us_day = us_now.date()
    from pathlib import Path
    if now < scheduled_kst_time(us_day):
        print("[news-ai] skipped reason=before_scheduled_time stock=%s" % stock_name, flush=True)
        return
    # Do not change the original news result or run a second news collection.
    import psycopg
    with psycopg.connect(_worker_database_url(store), connect_timeout=10, autocommit=True) as conn:
        batch = run_stock_batch(conn, [{
            "market": market_code, "symbol": stock_name,
            "name": stock_name, "exchange_day": us_day,
            "articles": raw,
        }])
        outcome = batch[0]
        print("[news-ai] stock=%s status=%s count=%s" % (
            stock_name, outcome["status"], outcome.get("issue_count", 0)), flush=True)
        ids = outcome.get("ids") or []
        if outcome["status"] == "already_reserved":
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT result->'issue_ids' FROM public.news_ai_call_ledger
                       WHERE market=%s AND symbol=%s AND exchange_day=%s
                         AND status='completed' LIMIT 1""",
                    (market_code, stock_name, us_day))
                row = cur.fetchone()
                ids = row[0] if row and row[0] else []
        if not ids:
            return
        with conn.cursor() as cur:
            cur.execute(
                "SELECT headline, summary, tags FROM public.news_ai_issues WHERE id=ANY(%s) ORDER BY id",
                (ids,))
            issues = [{"headline": row[0], "summary": row[1], "tags": row[2]} for row in cur.fetchall()]
        if not issues:
            return
        updated = with_ai_issue_briefs(
            result, issues, display_time=now.strftime("%Y-%m-%d %H:%M"),
            stock_names=[stock_name])
        store.save_snapshot(stock_name, fingerprint=fingerprint, result=updated, **params)
        print("[news-ai] snapshot_updated stock=%s count=%s model=%s" % (
            stock_name, len(issues), MODEL), flush=True)


def apply_unchanged_worker_ai(*, store, market, stock_name, raw, fingerprint, params):
    """Use the existing Neon snapshot when news is unchanged; no extra collection."""
    if market not in ("미국", "US"):
        return
    import psycopg
    with psycopg.connect(_worker_database_url(store), connect_timeout=10, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT result_payload FROM public.news_processed_snapshots
                   WHERE market=%s AND stock_name=%s AND result_limit=%s
                     AND storyboard_limit=%s AND display_timezone=%s
                     AND source_fingerprint=%s AND expires_at > now()
                   LIMIT 1""",
                (market, stock_name, params["limit"], params["storyboard_limit"],
                 params["display_timezone"], fingerprint))
            row = cur.fetchone()
    if row and isinstance(row[0], dict):
        apply_worker_ai(store=store, market=market, stock_name=stock_name,
                        raw=raw, fingerprint=fingerprint, result=row[0], params=params)
