"""Conservative staging cleanup.

Unprocessed source rows are never deleted. A source becomes purgeable only
after evidence was linked to an independently stored, durable issue record.
Cleanup runs opportunistically after a successful metadata storage batch.
"""
import logging
import os
from datetime import date
from threading import Lock

_LOG = logging.getLogger(__name__)
_LOCK = Lock()
_LAST_RUN_DAY = None


def purge_expired_processed_news(batch_size=500):
    """Delete at most batch_size expired, fully processed source rows.

    Related issue records and market reactions are not deleted; only temporary
    article metadata and dependent article links are deleted.
    """
    if os.environ.get("NEWS_RAW_CLEANUP_ENABLED") != "1":
        return 0
    if not os.environ.get("NEWS_DATABASE_URL"):
        return 0
    import psycopg
    statement = """
    WITH candidates AS (
      SELECT id FROM news_articles
      WHERE retention_expires_at <= now()
        AND processing_status='processed' AND processed_at IS NOT NULL
      ORDER BY retention_expires_at, id
      LIMIT %s
      FOR UPDATE SKIP LOCKED
    )
    DELETE FROM news_articles AS a USING candidates AS x
    WHERE a.id=x.id RETURNING a.id
    """
    with psycopg.connect(os.environ["NEWS_DATABASE_URL"], connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(statement, (batch_size,))
            return len(cur.fetchall())


def cleanup_once_per_day():
    """Try only once per server-day, only after a successful news batch."""
    global _LAST_RUN_DAY
    if os.environ.get("NEWS_RAW_CLEANUP_ENABLED") != "1":
        return
    today = date.today()
    if _LAST_RUN_DAY == today:
        return
    with _LOCK:
        if _LAST_RUN_DAY == today:
            return
        try:
            deleted = purge_expired_processed_news()
        except Exception as exc:
            _LOG.warning("temporary news cleanup deferred: %s", type(exc).__name__)
            return
        _LAST_RUN_DAY = today
        if deleted:
            _LOG.info("temporary news cleanup: deleted=%d expired processed rows", deleted)
