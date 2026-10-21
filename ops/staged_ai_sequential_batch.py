"""Sequential per-stock AI batch, staged only; not wired to production.

Uses existing Neon connection and reserves before any paid Groq request.
"""
import hashlib
import json
import urllib.error
from staged_daily_groq_issues import (analyze_news, build_model_news, recent_ai_articles,
                                      _has_verifiable_published_at, issue_source_metadata)


def has_eligible_ai_news(articles):
    """Require grounded, dated article text before reserving a paid request.

    Existing deterministic issue selection is NOT a prerequisite.
    """
    news, _ = build_model_news(recent_ai_articles(articles or []))
    return any(_has_verifiable_published_at(row.get("published_at")) for row in news)
from staged_ai_issue_store import save_ai_issues, read_issue_sources
from staged_daily_call_guard import reserve_once, finish_reservation


def _safe_failure_reason(exc):
    """Log a bounded error code only: never provider body, article or credentials."""
    if isinstance(exc, urllib.error.HTTPError):
        status = getattr(exc, "code", None)
        return f"http_{status}" if type(status) is int and 100 <= status <= 599 else "http_unknown"
    if isinstance(exc, urllib.error.URLError):
        return "http_connection"
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_json"
    if isinstance(exc, ValueError):
        return {
            "model_response_truncated": "model_truncated",
            "model_response_empty": "model_empty",
            "Invalid issue response": "invalid_json_shape",
            "Expected 0-3 issues": "invalid_issue_count",
            "Invalid fields": "invalid_issue_fields",
            "Invalid text": "invalid_issue_text",
            "Invalid tags": "invalid_issue_tags",
            "Invalid article source IDs": "invalid_source_ids",
            "Each AI issue requires its own real source articles": "missing_source_evidence",
            "Missing source title or publication timestamp": "invalid_source_metadata",
        }.get(str(exc), "validation_error")
    if isinstance(exc, (KeyError, IndexError, TypeError)):
        return "invalid_api_response"
    return "processing_error"


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
        # Production Groq receives only articles published in the last 24 hours.
        # Keep injected offline analyzers compatible with existing unit tests.
        if analyze is analyze_news:
            articles = recent_ai_articles(articles)
        usage = {}
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
            if analyze is analyze_news:
                issues = analyze(stock["name"], articles, usage_callback=usage.update)
            else:
                issues = analyze(stock["name"], articles)
            sources = issue_source_metadata(issues, articles)
            ids = save(conn, issues, market=market, symbol=symbol,
                       exchange_day=day, sources_by_issue=sources) if issues else []
            with conn.transaction():
                finish(conn, market=market, symbol=symbol, exchange_day=day,
                       request_hash=request_hash, status="completed",
                       result={"issue_ids": ids, "issue_count": len(issues),
                               **({"usage": usage} if usage else {})})
            results.append({"market": market, "symbol": symbol, "status": "ok",
                            "issue_count": len(issues), "ids": ids,
                            "issue_sources": sources})
        except Exception as exc:
            reason = _safe_failure_reason(exc)
            # Existing one-call-per-day reservation is preserved even on failure.
            print("[news-ai] failed stock=%s category=%s reason=%s" %
                  (symbol, type(exc).__name__, reason), flush=True)
            if reserved:
                try:
                    with conn.transaction():
                        finish(conn, market=market, symbol=symbol, exchange_day=day,
                               request_hash=request_hash, status="failed",
                               failure_category=type(exc).__name__,
                               failure_reason=reason,
                               result={"usage": usage} if usage else None)
                except Exception:
                    pass
            results.append({"market": market, "symbol": symbol, "status": "error",
                            "error_type": type(exc).__name__, "error_code": reason})
    return results


def _worker_database_url(store):
    """Use either configured Neon URL or the existing store connection method."""
    import os
    value = (os.environ.get("NEWS_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()
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
    if not isinstance(result, dict) or not has_eligible_ai_news(raw):
        print("[news-ai] skipped reason=no_dated_usable_article stock=%s" % stock_name, flush=True)
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
        sources = outcome.get("issue_sources") or []
        if outcome["status"] == "already_reserved":
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT result->'issue_ids', result->'issue_sources' FROM public.news_ai_call_ledger
                       WHERE market=%s AND symbol=%s AND exchange_day=%s
                         AND status='completed' LIMIT 1""",
                    (market_code, stock_name, us_day))
                row = cur.fetchone()
                ids = row[0] if row and row[0] else []
                sources = read_issue_sources(
                    conn, market=market_code, symbol=stock_name,
                    exchange_day=us_day, issue_ids=ids
                ) or (row[1] if row and row[1] else [])
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
            stock_names=[stock_name], sources_by_issue=sources,
            exchange_day=us_day)
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
