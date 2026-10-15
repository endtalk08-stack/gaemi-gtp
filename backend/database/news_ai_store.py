"""Neon-backed atomic AI call ledger and shared issue history.

Call reservations are serialized per stock / exchange-local date with a
transaction advisory lock. A failed or timed-out provider request still uses
one slot, so retries and worker restarts cannot exceed the daily budget.
"""
import logging
import os

_LOG = logging.getLogger(__name__)


def _url_hash(url):
    from .news_url import news_url_hash
    return news_url_hash(url)

def reserve_issue_call(market, stock, exchange_day, fingerprint):
    """Return (state, reusable_issues).

    state is reserved, cached, in_progress, exhausted or unavailable.
    Only reserved means a new provider call is authorized.
    """
    url = os.environ.get("NEWS_DATABASE_URL")
    if not url:
        return "unavailable", []
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=5) as connection:
            with connection.cursor() as cur:
                # Locks both competing workers and separate application instances.
                lock_key = "news-ai|" + market + "|" + stock + "|" + exchange_day
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))
                cur.execute(
                    "SELECT status,result FROM news_ai_call_ledger "
                    "WHERE market=%s AND symbol=%s AND exchange_day=%s AND request_hash=%s",
                    (market, stock, exchange_day, fingerprint),
                )
                existing = cur.fetchone()
                cur.execute(
                    "SELECT result FROM news_ai_call_ledger WHERE "
                    "market=%s AND symbol=%s AND exchange_day=%s AND status='completed' "
                    "AND result IS NOT NULL ORDER BY completed_at DESC LIMIT 1",
                    (market, stock, exchange_day),
                )
                latest = cur.fetchone()
                previous = latest[0] if latest and isinstance(latest[0], list) else []
                if existing:
                    saved = existing[1] if isinstance(existing[1], list) else []
                    return ("cached" if existing[0] == "completed" else "in_progress",
                            saved if saved else previous)
                cur.execute(
                    "SELECT count(*) FROM news_ai_call_ledger WHERE "
                    "market=%s AND symbol=%s AND exchange_day=%s",
                    (market, stock, exchange_day),
                )
                if cur.fetchone()[0] >= 3:
                    return "exhausted", previous
                cur.execute(
                    "INSERT INTO news_ai_call_ledger "
                    "(market,symbol,exchange_day,request_hash,status,provider,model_id) "
                    "VALUES (%s,%s,%s,%s,'reserved','groq',%s)",
                    (market, stock, exchange_day, fingerprint,
                     os.environ.get("NEWS_ISSUE_AI_MODEL", "openai/gpt-oss-20b")),
                )
        return "reserved", previous
    except Exception as exc:
        _LOG.warning("AI quota check failed; refusing provider call: %s", type(exc).__name__)
        return "unavailable", []


def complete_issue_call(market, stock, exchange_day, fingerprint, issues):
    """Persist AI result and event/article evidence in one transaction."""
    try:
        import psycopg
        from psycopg.types.json import Jsonb
        with psycopg.connect(os.environ["NEWS_DATABASE_URL"], connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE news_ai_call_ledger SET status='completed',result=%s,"
                    "completed_at=now() WHERE market=%s AND symbol=%s AND "
                    "exchange_day=%s AND request_hash=%s AND status='reserved'",
                    (Jsonb(issues), market, stock, exchange_day, fingerprint),
                )
                if cur.rowcount != 1:
                    raise ValueError("missing_AI_call_reservation")
                for issue in issues[:3]:
                    event_key = market + ":" + str(issue["event_key"])
                    cur.execute(
                        "INSERT INTO news_events(event_key,market,event_title) "
                        "VALUES (%s,%s,%s) ON CONFLICT(event_key) DO UPDATE "
                        "SET last_seen_at=now() RETURNING id",
                        (event_key, market, issue["headline"]),
                    )
                    event_id = cur.fetchone()[0]
                    cur.execute(
                        "INSERT INTO news_ai_issues "
                        "(market,symbol,exchange_day,event_id,headline,summary,tags,"
                        "material_type,material_direction,model_id) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        (market, stock, exchange_day, event_id, issue["headline"],
                         issue["summary"], Jsonb(issue["tags"]),
                         issue.get("material_type"), issue.get("material_direction"),
                         os.environ.get("NEWS_ISSUE_AI_MODEL", "openai/gpt-oss-20b")),
                    )
                    issue_id = cur.fetchone()[0]
                    for url in set(issue.get("source_urls") or []):
                        digest = _url_hash(url)
                        if not digest:
                            continue
                        # Durable issue evidence survives source staging cleanup.
                        from .news_url import canonical_news_url
                        canonical = canonical_news_url(url)
                        cur.execute(
                            "INSERT INTO news_issue_evidence(issue_id,url_hash,canonical_url) "
                            "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                            (issue_id, digest, canonical),
                        )
                        cur.execute(
                            "INSERT INTO news_ai_issue_sources(issue_id,article_id) "
                            "SELECT %s,id FROM news_articles WHERE url_hash=%s "
                            "ON CONFLICT DO NOTHING",
                            (issue_id, digest),
                        )
                        cur.execute(
                            "INSERT INTO news_event_articles(event_id,article_id) "
                            "SELECT %s,id FROM news_articles WHERE url_hash=%s "
                            "ON CONFLICT DO NOTHING",
                            (event_id, digest),
                        )
                        # Mark ONLY articles that have an independently
                        # persisted issue AND durable source URL evidence.
                        cur.execute(
                            "UPDATE news_articles SET processing_status='processed', "
                            "processed_at=now() WHERE url_hash=%s AND EXISTS "
                            "(SELECT 1 FROM news_issue_evidence "
                            "WHERE issue_id=%s AND url_hash=%s)",
                            (digest, issue_id, digest),
                        )
        return True
    except Exception as exc:
        _LOG.warning("AI issue persistence failed: %s", type(exc).__name__)
        return False


_FAILURE_CATEGORIES = {
    "api_error", "json_error", "validation_error", "db_error", "worker_error", "unknown"
}
_FAILURE_REASONS = {
    "invalid_json", "invalid_schema", "empty_issues", "invalid_entry",
    "invalid_source_ids", "invalid_headline", "invalid_summary",
    "invalid_tags", "invalid_category", "invalid_direction",
    "invalid_event_key", "duplicate_event_key", "unsupported_numbers",
    "no_accepted_issues", "validator_exception", "save_failed",
    "provider_exception", "timeout_or_connection", "http_error",
    "thread_start_failed", "unspecified"
}


def fail_issue_call(market, stock, exchange_day, fingerprint,
                    category="unknown", reason="unspecified"):
    """Spend the reserved slot and store *only* known-safe failure codes."""
    category = category if category in _FAILURE_CATEGORIES else "unknown"
    reason = str(reason or "unspecified")
    if reason not in _FAILURE_REASONS and not (
        reason.startswith("http_") and len(reason) == 8
        and reason[5:].isdigit() and reason[5] in ("4", "5")
    ):
        reason = "unspecified"
    status = "invalid" if category in ("json_error", "validation_error") else "failed"
    try:
        import psycopg
        with psycopg.connect(os.environ["NEWS_DATABASE_URL"], connect_timeout=5) as conn:
            conn.execute(
                "UPDATE news_ai_call_ledger SET status=%s, "
                "failure_category=%s,failure_reason=%s,completed_at=now() "
                "WHERE market=%s AND symbol=%s AND exchange_day=%s "
                "AND request_hash=%s AND status='reserved'",
                (status, category, reason, market, stock, exchange_day, fingerprint),
            )
    except Exception as exc:
        _LOG.warning("AI failure diagnostic persistence unavailable: %s",
                     type(exc).__name__)
