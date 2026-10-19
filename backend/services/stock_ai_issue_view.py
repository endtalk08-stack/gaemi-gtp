"""Read-only AI issue view shared by fixed-stock watchlist and analysis body.

Existing news_ai_issues contains verified AI outputs keyed by historic names.
Resolve those names to the exact 40 market+symbols, without rewriting history,
running AI, fetching articles, or touching market ranking tables.
"""
import os
from datetime import datetime, timezone

from .stock_scope import STOCKS, resolve_stock

MAX_ISSUES_PER_STOCK = 3


def read_ai_issue_map(database_url=None, *, strict=False):
    """Fetch existing AI-issued title/body together. Failure -> empty map."""
    empty = {(r["market"], r["symbol"]): [] for r in STOCKS}
    db = database_url if database_url is not None else os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not db:
        if strict:
            raise RuntimeError("neon_database_not_configured")
        return empty
    aliases = list(dict.fromkeys(
        alias for r in STOCKS for alias in r["aliases"]
        if alias and len(alias) <= 90
    ))
    try:
        import psycopg
        with psycopg.connect(db, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, market, symbol, headline, summary, generated_at
                       FROM public.news_ai_issues
                       WHERE market = ANY(%s) AND symbol = ANY(%s)
                         AND generated_at >= now() - interval '24 hours'
                       ORDER BY generated_at DESC, id DESC
                       LIMIT 800""",
                    (["US", "KR"], aliases),
                )
                results = cur.fetchall()
    except Exception as exc:
        print("[stock-issues] neon_read_failed=" + type(exc).__name__, flush=True)
        if strict:
            raise RuntimeError("stock_ai_issues_read_unavailable") from exc
        return empty
    for issue_id, market, old_symbol, headline, summary, generated_at in results:
        stock = resolve_stock(old_symbol, market=market)
        if stock is None:
            continue
        key = (stock["market"], stock["symbol"])
        if len(empty[key]) >= MAX_ISSUES_PER_STOCK:
            continue
        title = str(headline or "").strip()
        body = str(summary or "").strip()
        if not title or not body:
            continue
        empty[key].append({
            "id": int(issue_id),
            "market": stock["market"],
            "symbol": stock["symbol"],
            "headline": title,
            "summary": body,
            "generated_at": generated_at.astimezone(timezone.utc).isoformat()
            if isinstance(generated_at, datetime) and generated_at.tzinfo else str(generated_at or ""),
        })
    return empty


def read_stock_ai_issues(market, symbol):
    stock = resolve_stock(None, market=market, symbol=symbol)
    if stock is None:
        return None
    return read_ai_issue_map().get((stock["market"], stock["symbol"]), [])


def _read_fixed_watchlist_registry():
    """Read only the 40 approved company identities from independent Neon table."""
    db = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not db:
        return None
    try:
        import psycopg
        with psycopg.connect(db, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT market, symbol, display_name
                       FROM public.fixed_watchlist_stocks
                       ORDER BY CASE market WHEN 'KR' THEN 0 ELSE 1 END,
                                position ASC"""
                )
                rows = cur.fetchall()
    except Exception as exc:
        print("[fixed40-watchlist] neon_read_failed=" + type(exc).__name__, flush=True)
        return None
    if len(rows) != len(STOCKS):
        return None
    actual = [(m, s, n) for m, s, n in rows]
    expected = [(r["market"], r["symbol"], r["name"]) for r in STOCKS]
    if actual != expected:
        print("[fixed40-watchlist] registry_not_matching_verified_list", flush=True)
        return None
    return [{"market": m, "symbol": s, "name": n} for m, s, n in rows]


def build_watchlist_result():
    """Neon-approved 40 names plus saved AI issue titles/bodies, never prices."""
    registered = _read_fixed_watchlist_registry()
    if registered is None:
        return None
    issues = read_ai_issue_map(strict=True)
    return [{
        **row,
        "issues": issues[(row["market"], row["symbol"])],
    } for row in registered]
