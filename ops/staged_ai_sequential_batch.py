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


def apply_worker_ai(*, store, market, stock_name, raw, fingerprint, result, params):
    """Run at most one AI analysis per stock/day after original snapshot is saved."""
    import os
    from datetime import datetime
    from zoneinfo import ZoneInfo
    if not os.environ.get("GROQ_API_KEY", "").strip():
        print("[news-ai] skipped reason=missing_groq_key", flush=True)
        return
    market_code = "US" if market in ("미국", "US") else "KR" if market in ("국내", "KR") else None
    if market_code is None:
        return
    if market_code != "US":
        return
    # Reuse the worker's explicit stock selection; never include ranking extras.
    configured = os.environ.get("NEWS_WORKER_STOCKS", "")
    selected_us = {
        item.partition(":")[2].strip()
        for item in configured.split(",")
        if item.strip().startswith("미국:")
    }
    if stock_name not in selected_us:
        print("[news-ai] skipped reason=outside_worker_us_selection stock=%s" % stock_name, flush=True)
        return
    if not isinstance(result, dict) or not result.get("issue_briefs"):
        print("[news-ai] skipped reason=no_selected_issue stock=%s" % stock_name, flush=True)
        return
    from staged_ai_snapshot_integration import with_ai_issue_briefs
    from staged_daily_groq_issues import MODEL
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    # Do not change the original news result or run a second news collection.
    import psycopg
    with psycopg.connect(store.database_url(), connect_timeout=10, autocommit=True) as conn:
        batch = run_stock_batch(conn, [{
            "market": market_code, "symbol": stock_name,
            "name": stock_name, "exchange_day": now.date(),
            "articles": raw,
        }])
        outcome = batch[0]
        print("[news-ai] stock=%s status=%s count=%s" % (
            stock_name, outcome["status"], outcome.get("issue_count", 0)), flush=True)
        if outcome["status"] != "ok" or not outcome.get("ids"):
            return
        with conn.cursor() as cur:
            cur.execute(
                "SELECT headline, summary, tags FROM public.news_ai_issues WHERE id=ANY(%s) ORDER BY id",
                (outcome["ids"],))
            issues = [{"headline": row[0], "summary": row[1], "tags": row[2]} for row in cur.fetchall()]
        updated = with_ai_issue_briefs(
            result, issues, display_time=now.strftime("%Y-%m-%d %H:%M"),
            stock_names=[stock_name])
        store.save_snapshot(stock_name, fingerprint=fingerprint, result=updated, **params)
        print("[news-ai] snapshot_updated stock=%s count=%s model=%s" % (
            stock_name, len(issues), MODEL), flush=True)
