"""Neon 24-hour store for *news issue briefs*, not stock analysis snapshots.

Persist only the already-generated central-news issue briefs (headline, visible
summary, tags and timestamps). Raw articles, full article bodies, price/supply
analysis and permanent market events are deliberately out of scope.
"""
import json
import os

_RESULT_TYPE = "stock_news_issue_briefs_v1"


def _url():
    return os.getenv("NEWS_DATABASE_URL", "").strip()


def _market_code(market):
    return "kr" if market in ("kr", "국내") else "us" if market in ("us", "미국") else ""


def _key(market, stock_name):
    return json.dumps([_market_code(market), str(stock_name).strip()],
                      ensure_ascii=False, separators=(",", ":"))


def _briefs_for_storage(briefs):
    """Copy only the fields already displayed by the central-news issue block."""
    selected = []
    if not isinstance(briefs, list):
        return selected
    for brief in briefs[:3]:
        if not isinstance(brief, dict):
            continue
        headline = str(brief.get("headline") or "").strip()
        summary = str(brief.get("summary") or "").strip()
        if not headline or not summary:
            continue
        selected.append({
            "headline": headline[:250],
            "summary": summary[:4000],
            "tags": [str(tag)[:100] for tag in (brief.get("tags") or [])[:8]
                     if isinstance(tag, str)],
            "time": str(brief.get("time") or "")[:80],
            "reaction_at": str(brief.get("reaction_at") or "")[:90],
            "stock_names": [str(name)[:100] for name in (brief.get("stock_names") or [])[:6]
                            if isinstance(name, str)],
        })
    return selected


def read_issue_briefs_batch(market, rows):
    """One DB roundtrip to fetch 20 existing central-news results."""
    if not rows or not _url() or not _market_code(market):
        return {}
    keys = [_key(market, row["name"]) for row in rows]
    try:
        import psycopg
        with psycopg.connect(_url(), connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT result_key, result_payload
                    FROM public.news_processed_results_24h
                    WHERE result_type = %s AND result_key = ANY(%s)
                      AND expires_at > now()
                """, (_RESULT_TYPE, keys))
                records = cur.fetchall()
        result = {}
        for key, payload in records:
            if not isinstance(payload, dict):
                continue
            briefs = _briefs_for_storage(payload.get("issue_briefs"))
            if briefs:
                result[key] = briefs
        return result
    except Exception as exc:
        print(f"[processed news] read failed: {type(exc).__name__}", flush=True)
        return {}


def save_issue_briefs(stock_name, market, briefs):
    """Save the central display block only, expiring no later than 24 hours."""
    if not _url() or not _market_code(market):
        return False
    selected = _briefs_for_storage(briefs)
    if not selected:
        return False
    payload = json.dumps({"issue_briefs": selected}, ensure_ascii=False)
    try:
        import psycopg
        with psycopg.connect(_url(), connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.news_processed_results_24h
                        (result_type, result_key, result_payload, created_at, expires_at)
                    VALUES (%s, %s, %s::jsonb, now(), now() + interval '24 hours')
                    ON CONFLICT (result_type, result_key)
                    DO UPDATE SET result_payload = excluded.result_payload,
                                  created_at = excluded.created_at,
                                  expires_at = excluded.expires_at
                """, (_RESULT_TYPE, _key(market, stock_name), payload))
        return True
    except Exception as exc:
        print(f"[processed news] save failed: {type(exc).__name__}", flush=True)
        return False
