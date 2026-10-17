"""Neon transport for derived stock-news results.

Independent of original news_articles; no UI effects.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

RETENTION_HOURS = 24

def database_url():
    return os.environ.get("NEWS_DATABASE_URL", "").strip()

def _connection_failure_category(exc):
    """Diagnostic category only: never expose DB URLs or credentials."""
    message = str(exc).lower()
    if "password authentication failed" in message or "28p01" in message:
        return "authentication"
    if "no such host" in message or "could not translate host" in message or "name resolution" in message:
        return "dns"
    if "timeout" in message or "timed out" in message:
        return "timeout"
    if "too many connections" in message or "too many clients" in message:
        return "connection_limit"
    if any(x in message for x in ("certificate verify failed", "hostname mismatch", "self-signed certificate")):
        return "certificate"
    if any(x in message for x in ("ssl syscall", "unexpected eof", "connection reset", "server closed the connection")):
        return "transport_reset"
    if "ssl" in message or "tls" in message:
        return "tls"
    if "connection refused" in message or "network is unreachable" in message:
        return "network"
    return "other"


def _connect():
    import psycopg
    url = database_url()
    if not url:
        raise RuntimeError("NEWS_DATABASE_URL is not configured")
    # Neon connect time can vary; the original five-second timeout dropped
    # connections while the same service user succeeded with ten seconds.
    for attempt in (1, 2, 3):
        try:
            return psycopg.connect(url, connect_timeout=10)
        except psycopg.OperationalError as exc:
            category = _connection_failure_category(exc)
            print(f"[processed news] db_connect_failed category={category} attempt={attempt}", flush=True)
            # Temporary SSL transport drops must be retried, not treated
            # as invalid credentials. Never retry bad authentication/certs.
            if attempt == 3 or category in ("authentication", "certificate"):
                raise
            time.sleep(attempt)

def purge_expired_original_news():
    """Delete expired Naver original news, leaving derived result tables intact."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM public.news_articles
                WHERE source_id IN (
                    SELECT id FROM public.news_sources
                    WHERE source_key = 'naver'
                )
                  AND (
                    retention_expires_at <= now()
                    OR COALESCE(published_at, collected_at)
                       <= now() - interval '24 hours'
                  )
            """)
            return cur.rowcount


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


def _recent_existing_issue_briefs(previous, stock_name):
    """Keep only the same stock's genuinely recent event briefs."""
    from datetime import datetime, timezone, timedelta
    if not isinstance(previous, dict):
        return []
    now = datetime.now(timezone.utc)
    retained = []
    for item in previous.get("issue_briefs") or []:
        if not isinstance(item, dict):
            continue
        if stock_name not in (item.get("stock_names") or []):
            continue
        stamp = str(item.get("reaction_at") or "").strip()
        try:
            published = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if published.tzinfo is None:
                continue
            age = now - published.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
        if timedelta(0) <= age < timedelta(hours=24):
            retained.append(item)
    return retained


def save_snapshot(stock_name, *, market, limit, storyboard_limit,
                  display_timezone, fingerprint, result):
    """Atomic upsert; never write unsuccessful analysis."""
    from psycopg.types.json import Jsonb
    if result.get("_news_status") != "ok":
        raise ValueError("refusing to save failed analysis")
    normalized = json.loads(json.dumps(result, ensure_ascii=False, default=str))
    # Issue ownership is enforced at the storage boundary. A brief assigned to
    # a different ticker must never appear in this stock's headline/sidebar.
    submitted = normalized.get("issue_briefs") or []
    valid = [
        brief for brief in submitted
        if isinstance(brief, dict)
        and stock_name in (brief.get("stock_names") or [])
    ]
    if len(valid) != len(submitted):
        print(
            f"[news-worker] unrelated_issues_rejected stock={stock_name} count={len(submitted)-len(valid)}",
            flush=True,
        )
    normalized["issue_briefs"] = valid
    with _connect() as conn:
        with conn.cursor() as cur:
            # A temporary zero-result verification pass must not erase a
            # still-valid, already selected issue. This does NOT keep expired,
            # unrelated, or unverified older issue briefs.
            if not normalized.get("issue_briefs"):
                cur.execute("""
                    SELECT result_payload FROM public.news_processed_snapshots
                    WHERE market=%s AND stock_name=%s AND result_limit=%s
                    AND storyboard_limit=%s AND display_timezone=%s
                    AND expires_at>now()
                    FOR UPDATE
                """, (market, stock_name, limit, storyboard_limit, display_timezone))
                previous = cur.fetchone()
                preserved = _recent_existing_issue_briefs(
                    previous[0] if previous else None, stock_name
                )
                if preserved:
                    normalized["issue_briefs"] = preserved
                    print(
                        f"[news-worker] preserved_recent_issues stock={stock_name} count={len(preserved)}",
                        flush=True,
                    )
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
