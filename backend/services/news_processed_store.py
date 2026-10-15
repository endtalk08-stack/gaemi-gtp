"""Neon transport for derived stock-news results.

Independent of original news_articles; no UI effects.
"""
from __future__ import annotations

import hashlib
import json
import os

RETENTION_HOURS = 24

def database_url():
    return os.environ.get("NEWS_DATABASE_URL", "").strip()

def _connect():
    import psycopg
    url = database_url()
    if not url:
        raise RuntimeError("NEWS_DATABASE_URL is not configured")
    return psycopg.connect(url, connect_timeout=5)

def source_fingerprint(rows):
    """Order-independent; new/updated articles cause a different digest."""
    material = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        material.append([str(row.get(key) or "") for key in
                         ("url", "link", "originallink", "title", "description", "pubDate")])
    material.sort()
    return hashlib.sha256(json.dumps(
        material, ensure_ascii=False, separators=(",", ":")
    ).encode()).hexdigest()

def read_signature(stock_name, market, limit, storyboard_limit, display_timezone):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source_fingerprint FROM public.news_processed_snapshots
                WHERE market=%s AND stock_name=%s AND result_limit=%s
                AND storyboard_limit=%s AND display_timezone=%s
                AND expires_at>now() LIMIT 1
            """, (market, stock_name, limit, storyboard_limit, display_timezone))
            row = cur.fetchone()
            return row[0] if row else None

def read_snapshot(stock_name, *, market, limit=50, storyboard_limit=3,
                  display_timezone="Asia/Seoul"):
    """Only return results from a worker that has checked this stock recently."""
    if not database_url():
        return None
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT result_payload FROM public.news_processed_snapshots
                    WHERE market=%s AND stock_name=%s AND result_limit=%s
                    AND storyboard_limit=%s AND display_timezone=%s
                    AND expires_at>now()
                    AND checked_at>now()-interval '20 minutes'
                    LIMIT 1
                """, (market, stock_name, limit, storyboard_limit, display_timezone))
                row = cur.fetchone()
                return row[0] if row and isinstance(row[0], dict) else None
    except Exception as exc:
        print(f"[processed news] read_failed={type(exc).__name__}", flush=True)
        return None

def mark_checked(stock_name, *, market, limit, storyboard_limit, display_timezone):
    """Refresh health without redoing unchanged analysis."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE public.news_processed_snapshots SET checked_at=now()
                WHERE market=%s AND stock_name=%s AND result_limit=%s
                AND storyboard_limit=%s AND display_timezone=%s AND expires_at>now()
            """, (market, stock_name, limit, storyboard_limit, display_timezone))

def save_snapshot(stock_name, *, market, limit, storyboard_limit,
                  display_timezone, fingerprint, result):
    """Atomic upsert; never write unsuccessful analysis."""
    from psycopg.types.json import Jsonb
    if result.get("_news_status") != "ok":
        raise ValueError("refusing to save failed analysis")
    normalized = json.loads(json.dumps(result, ensure_ascii=False, default=str))
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.news_processed_snapshots
                    (market,stock_name,result_limit,storyboard_limit,display_timezone,
                     source_fingerprint,result_payload,processed_at,checked_at,expires_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,now(),now(),now()+interval '24 hours')
                ON CONFLICT (market,stock_name,result_limit,storyboard_limit,display_timezone)
                DO UPDATE SET source_fingerprint=EXCLUDED.source_fingerprint,
                    result_payload=EXCLUDED.result_payload, processed_at=now(),
                    checked_at=now(), expires_at=EXCLUDED.expires_at
            """, (market, stock_name, limit, storyboard_limit, display_timezone,
                  fingerprint, Jsonb(normalized)))

def purge_expired():
    """Delete only expired derived results, not original news."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.news_processed_snapshots WHERE expires_at<=now()")
            return cur.rowcount
