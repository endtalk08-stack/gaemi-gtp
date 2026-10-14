"""Neon/PostgreSQL persistence for the market-wide US closing brief.

One final brief per confirmed NY trading session. No collection occurs here:
the existing market-specific builder creates the result, the background job
writes it, and the central chat reads the same stored data.
"""
import datetime
import os


def is_store_configured():
    return bool(os.environ.get("DATABASE_URL", "").strip())


def _connection():
    import psycopg
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5)


def get_latest_us_close_brief():
    """Return the newest stored result, or None if not configured or empty.

    Let connection/query errors propagate when configured, so the API does not
    silently start repeatedly collecting fresh news on a database outage.
    """
    if not is_store_configured():
        return None
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM us_market_close_results "
                "ORDER BY session_date DESC LIMIT 1"
            )
            row = cur.fetchone()
    return row[0] if row else None


def get_us_close_brief_for_session(session):
    if not is_store_configured():
        return None
    session_date = session if isinstance(session, datetime.date) else datetime.date.fromisoformat(str(session))
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM us_market_close_results WHERE session_date = %s",
                (session_date,)
            )
            row = cur.fetchone()
    return row[0] if row else None


def save_us_close_brief(brief):
    """Insert once (atomic PK dedupe); never replace an already published day."""
    if not is_store_configured():
        raise RuntimeError("DATABASE_URL is not configured")
    session = datetime.date.fromisoformat(str(brief["session_date"]))
    index_count = len([
        item for item in brief.get("indices", [])
        if item.get("date") == session.isoformat()
        and item.get("name") in {"나스닥", "S&P500", "다우"}
    ])
    article_count = len([
        item for item in brief.get("article_sources", [])
        if item.get("url")
    ])
    if not brief.get("ok") or index_count != 3 or article_count < 1:
        raise ValueError("US close brief requires all three confirmed indices and an original article")

    from psycopg.types.json import Jsonb
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO us_market_close_results "
                "(session_date, source, index_count, article_count, payload) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (session_date) DO NOTHING RETURNING session_date",
                (session, "yahoo_daily+naver", index_count, article_count, Jsonb(brief))
            )
            inserted = cur.fetchone() is not None
    return inserted
