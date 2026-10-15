"""24-hour processed-news results in Neon, separate from raw news and permanent records.

Only the market_issue_headline result type is wired today. No Redis, AI, article-body
storage, permanent-record writes, or new data collection takes place here.
"""
import json
import os
import threading

from backend.analysis.news.catalog import STOCK_UNIVERSE

_RESULT_TYPE = "market_issue_headline"
_cleanup_lock = threading.Lock()
_cleanup_started = False
_cleanup_wakeup = threading.Event()


def _url():
    return os.getenv("NEWS_DATABASE_URL", "").strip()


def _key(market, row):
    return json.dumps([market, row["symbol"], row["name"]], ensure_ascii=False, separators=(",", ":"))


def _start_expiry_cleanup():
    """Delete only expired processed records hourly; never touch raw or permanent data."""
    global _cleanup_started
    if not _url():
        return
    with _cleanup_lock:
        if _cleanup_started:
            return
        worker = threading.Thread(target=_cleanup_loop, daemon=True, name="processed-news-expiry")
        worker.start()
        _cleanup_started = True


def _cleanup_loop():
    while True:
        try:
            import psycopg
            with psycopg.connect(_url(), connect_timeout=3) as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM public.news_processed_results_24h WHERE expires_at <= now()")
        except Exception as exc:
            print(f"[processed news] expiry cleanup failed: {type(exc).__name__}", flush=True)
        _cleanup_wakeup.wait(60 * 60)


def read_issue_headlines(market, rows):
    """Batch-fetch the not-yet-expired headline results in one SQL read."""
    _start_expiry_cleanup()
    if not _url() or not rows:
        return {}
    keys = [_key(market, row) for row in rows]
    try:
        import psycopg
        with psycopg.connect(_url(), connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT result_key, result_payload
                    FROM public.news_processed_results_24h
                    WHERE result_type = %s AND result_key = ANY(%s)
                      AND expires_at > now()
                      AND created_at > now() - interval '15 minutes'
                """, (_RESULT_TYPE, keys))
                found = cur.fetchall()
        return {
            key: str(payload.get("headline") or "").strip()
            for key, payload in found
            if isinstance(payload, dict) and str(payload.get("headline") or "").strip()
        }
    except Exception as exc:
        print(f"[processed news] cache read failed: {type(exc).__name__}", flush=True)
        return {}


def _aliases(name):
    aliases = [name]
    for universe in STOCK_UNIVERSE.values():
        if name in universe:
            aliases.extend(universe[name])
            break
    # No broad one-character match that can pull unrelated companies' news.
    return {str(s).strip().casefold() for s in aliases if len(str(s).strip()) >= 2}


def read_news_metadata_for_stocks(rows):
    """One Neon query for up to 20 stocks. Never fetch external URLs or run AI."""
    if not _url():
        return None
    stock_aliases = {row["symbol"]: _aliases(row["name"]) for row in rows}
    all_queries = sorted({q for aliases in stock_aliases.values() for q in aliases})
    if not all_queries:
        return {row["symbol"]: [] for row in rows}
    try:
        import psycopg
        with psycopg.connect(_url(), connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.headline, a.excerpt, a.canonical_url, a.published_at,
                           a.source_payload
                    FROM public.news_articles a
                    JOIN public.news_sources s ON s.id = a.source_id
                    WHERE s.source_key = 'naver'
                      AND a.retention_expires_at > now()
                      AND COALESCE(a.published_at, a.collected_at) > now() - interval '24 hours'
                      AND (lower(a.source_payload->>'query') = ANY(%s)
                           OR a.source_payload->'queries' ?| %s)
                    ORDER BY a.published_at DESC NULLS LAST, a.collected_at DESC
                    LIMIT 2000
                """, (all_queries, all_queries))
                found = cur.fetchall()
        result = {row["symbol"]: [] for row in rows}
        for title, excerpt, url, published, source in found:
            source = source if isinstance(source, dict) else {}
            queries = {str(source.get("query") or "").casefold()}
            queries.update(str(q).casefold() for q in (source.get("queries") or []) if isinstance(q, str))
            item = {
                "title": str(title or ""), "description": str(excerpt or ""),
                "url": str(url or ""), "published_at": published.isoformat() if published else "",
            }
            for row in rows:
                if queries.intersection(stock_aliases[row["symbol"]]):
                    result[row["symbol"]].append(item)
        return result
    except Exception as exc:
        print(f"[processed news] source metadata read failed: {type(exc).__name__}", flush=True)
        return None


def save_issue_headlines(market, entries):
    """Store only verified short derived results, with 24h expiry and no full bodies."""
    if not entries or not _url():
        return False
    _start_expiry_cleanup()
    params = [
        (_RESULT_TYPE, _key(market, row), json.dumps(payload, ensure_ascii=False))
        for row, payload in entries
        if isinstance(payload, dict) and str(payload.get("headline") or "").strip()
    ]
    if not params:
        return False
    try:
        import psycopg
        with psycopg.connect(_url(), connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO public.news_processed_results_24h
                        (result_type, result_key, result_payload, created_at, expires_at)
                    VALUES (%s, %s, %s::jsonb, now(), now() + interval '24 hours')
                    ON CONFLICT (result_type, result_key)
                    DO UPDATE SET result_payload = EXCLUDED.result_payload,
                                  created_at = EXCLUDED.created_at,
                                  expires_at = EXCLUDED.expires_at
                """, params)
        return True
    except Exception as exc:
        print(f"[processed news] save failed: {type(exc).__name__}", flush=True)
        return False
