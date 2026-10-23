"""Reconcile completed AI results without launching another Groq path.

The per-stock worker (apply_worker_ai) is the ONLY AI execution entrypoint.
This end-of-cycle maintenance keeps successful paid results visible in Neon.
"""
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo


NEW_YORK = ZoneInfo("America/New_York")
SEOUL = ZoneInfo("Asia/Seoul")
def due_exchange_day(now=None):
    now = now or datetime.now(NEW_YORK)
    local = now.astimezone(NEW_YORK)
    if local.time() < time(10, 30):
        return None
    return local.date()


# A completed, already paid Groq response may be persisted to the ledger but
# miss the display snapshot if an exception occurs afterward.  Reconcile using
# the verified, 24-hour issue/source bundle; NEVER call Groq again.
_RECONCILE_DISPLAY_SQL = """
WITH source_rows AS (
  SELECT s.stock_name, l.completed_at, l.exchange_day,
         b.result_payload->'issues' AS stored_issues,
         l.result->'issue_ids' AS ledger_ids
  FROM public.news_processed_snapshots s
  JOIN public.news_ai_call_ledger l
    ON l.market='US' AND l.symbol=s.stock_name
   AND l.exchange_day=%s AND l.status='completed'
  JOIN public.news_processed_results_24h b
    ON b.result_type='stock_ai_issue_sources_v1'
   AND b.result_payload->>'symbol'=s.stock_name
   AND b.result_payload->>'exchange_day'=l.exchange_day::text
   AND b.expires_at>now()
  WHERE s.market='미국'
    AND s.expires_at>now()
    AND jsonb_typeof(b.result_payload->'issues')='array'
    AND jsonb_array_length(b.result_payload->'issues') = jsonb_array_length(l.result->'issue_ids')
    AND NOT (s.result_payload ? '_ai_issue_briefs')
    AND NOT EXISTS (
       SELECT 1
       FROM jsonb_array_elements(
           CASE WHEN jsonb_typeof(s.result_payload->'issue_briefs')='array'
           THEN s.result_payload->'issue_briefs' ELSE '[]'::jsonb END
       ) visible
       JOIN public.news_ai_issues a ON a.market='US'
          AND a.symbol=s.stock_name AND a.exchange_day=l.exchange_day
          AND a.headline=visible->>'headline'
    )
),
ai AS (
  SELECT r.stock_name, r.exchange_day,
    jsonb_agg(jsonb_build_object(
      'headline', i->>'headline',
      'summary', i->>'summary',
      'direction', i->>'direction',
      'tags', i->'tags',
      'stock_names', jsonb_build_array(r.stock_name),
      'reaction_at', '',
      'time', CASE
          WHEN COALESCE(i->'source_articles'->0->>'published_at','') <> ''
          THEN to_char((i->'source_articles'->0->>'published_at')::timestamptz AT TIME ZONE 'Asia/Seoul',
                        'HH24:MI')
          ELSE ''
      END,
      'source_articles', (
         SELECT COALESCE(jsonb_agg(jsonb_build_object(
           'title',a->>'title','published_at',a->>'published_at',
           'source',a->>'source','url',a->>'url'
         )), '[]'::jsonb)
         FROM jsonb_array_elements(COALESCE(i->'source_articles','[]'::jsonb)) a
      )
    ) ORDER BY (i->>'issue_id')::bigint) AS ai_briefs,
    count(*) AS records
  FROM source_rows r
  CROSS JOIN LATERAL jsonb_array_elements(r.stored_issues) i
  WHERE (i->'source_articles') IS NOT NULL
    AND (i->>'issue_id')::bigint IN (
        SELECT value::bigint FROM jsonb_array_elements_text(r.ledger_ids)
    )
  GROUP BY r.stock_name,r.exchange_day
)
UPDATE public.news_processed_snapshots s
SET result_payload =
   jsonb_set(
     jsonb_set(
       jsonb_set(s.result_payload, '{_code_issue_briefs}',
                 COALESCE(s.result_payload->'_code_issue_briefs',
                          s.result_payload->'issue_briefs','[]'::jsonb),true),
       '{_ai_issue_briefs}',ai.ai_briefs,true),
     '{issue_briefs}',ai.ai_briefs,true)
   || jsonb_build_object('_ai_exchange_day',ai.exchange_day::text)
FROM ai
WHERE s.market='미국' AND s.stock_name=ai.stock_name
  AND s.expires_at>now() AND ai.records>0
  AND NOT (s.result_payload ? '_ai_issue_briefs')
RETURNING s.stock_name
"""


def reconcile_completed_ai_snapshots(conn, day):
    """Restore missing AI display strictly from already completed paid calls."""
    with conn.cursor() as cur:
        cur.execute(_RECONCILE_DISPLAY_SQL, (day,))
        return [row[0] for row in cur.fetchall()]


def process_due_ai_snapshots():
    """Reconcile completed AI snapshots only; never initiate/reserve paid calls.

    The original worker invokes apply_worker_ai for changed and unchanged news.
    This end-of-cycle function repairs display persistence after a completed
    Groq response, without reading panel news to initiate a second analysis.
    The return value remains zero so the worker cannot report it as new AI work.
    """
    day = due_exchange_day()
    if day is None:
        return 0
    db_url = (os.environ.get("NEWS_DATABASE_URL") or
              os.environ.get("DATABASE_URL") or "").strip()
    if not db_url:
        print("[news-ai] reconcile skipped reason=missing_neon_url", flush=True)
        return 0

    import psycopg
    try:
        with psycopg.connect(db_url, connect_timeout=10, autocommit=True) as conn:
            restored = reconcile_completed_ai_snapshots(conn, day)
    except Exception as exc:
        print("[news-ai] reconcile_failed category=%s" % type(exc).__name__, flush=True)
        return 0

    if restored:
        print("[news-ai] restored_completed_snapshots count=%s" % len(restored),
              flush=True)
    return 0
