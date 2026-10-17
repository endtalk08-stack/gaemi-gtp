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
