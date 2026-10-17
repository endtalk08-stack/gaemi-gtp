"""Sequential per-stock AI batch, staged only; worker invokes this after news collection.

Reuses the existing Neon connection; never schedules itself or changes snapshots.
"""
from staged_daily_groq_issues import analyze_news
from staged_ai_issue_store import save_ai_issues


def run_stock_batch(conn, stocks, *, analyze=analyze_news, save=save_ai_issues):
    """Process one stock at a time; fail closed on an individual stock error.

    stocks: iterable of {name, articles, market, symbol, exchange_day}.
    The caller owns scheduling, per-day idempotency and the DB connection.
    """
    results = []
    for stock in stocks:
        market, symbol = stock["market"], stock["symbol"]
        try:
            articles = stock.get("articles") or []
            issues = analyze(stock["name"], articles) if articles else []
            ids = save(conn, issues, market=market, symbol=symbol,
                       exchange_day=stock["exchange_day"]) if issues else []
            results.append({"market": market, "symbol": symbol, "status": "ok",
                            "issue_count": len(issues), "ids": ids})
        except Exception as exc:
            results.append({"market": market, "symbol": symbol, "status": "error",
                            "error_type": type(exc).__name__})
    return results
