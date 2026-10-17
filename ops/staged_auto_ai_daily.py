"""Scheduled US news AI processing within the existing DigitalOcean news worker.

Runs at most two eligible stocks per worker cycle after 10:30 New York time.
Neon call ledger guarantees at most one paid Groq attempt per stock/day.
Uses the existing, unexpired same-day news snapshots; does not re-collect news.
"""
import json
import os
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from staged_ai_sequential_batch import run_stock_batch, has_eligible_ai_news
from staged_ai_snapshot_integration import with_ai_issue_briefs

NEW_YORK = ZoneInfo("America/New_York")
SEOUL = ZoneInfo("Asia/Seoul")
APPROVED_US = (
    "TSMC ADR", "네비우스 그룹", "마이크로소프트", "마이크론 테크놀로지",
    "메타", "모더나", "브로드컴", "샌디스크", "스페이스X", "아마존닷컴",
    "아이렌", "아이온큐", "알파벳 Class A", "애플", "엔비디아",
    "오라클", "인텔", "일라이 릴리", "코어위브", "테슬라",
    "팔란티어 테크놀로지스",
)


def due_exchange_day(now=None):
    now = now or datetime.now(NEW_YORK)
    local = now.astimezone(NEW_YORK)
    if local.time() < time(10, 30):
        return None
    return local.date()


def _load_key():
    if os.environ.get("GROQ_API_KEY", "").strip():
        return True
    try:
        key = Path(__file__).with_name(".groq_api_key").read_text().strip()
    except (OSError, UnicodeError):
        return False
    if not key:
        return False
    os.environ["GROQ_API_KEY"] = key
    return True


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
  WHERE s.market='미국' AND s.stock_name=ANY(%s)
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
      'tags', i->'tags',
      'stock_names', jsonb_build_array(r.stock_name),
      'reaction_at', '',
      'time', CASE
          WHEN COALESCE(i->'source_articles'->0->>'published_at','') <> ''
          THEN to_char((i->'source_articles'->0->>'published_at')::timestamptz AT TIME ZONE 'Asia/Seoul',
                        'HH24:MI')
          ELSE to_char(r.completed_at AT TIME ZONE 'Asia/Seoul','HH24:MI')
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
        cur.execute(_RECONCILE_DISPLAY_SQL, (day, list(APPROVED_US)))
        return [row[0] for row in cur.fetchall()]


def process_due_ai_snapshots():
    """Poll eligible same-day snapshots after US 10:30; persist then display.

    Returns the number of stocks actually analyzed in this pass.
    The caller owns error isolation; no extra worker or timer is created.
    """
    day = due_exchange_day()
    if day is None:
        return 0
    if not _load_key():
        print("[news-ai] scheduled skipped reason=missing_groq_key", flush=True)
        return 0
    db_url = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not db_url:
        print("[news-ai] scheduled skipped reason=missing_neon_url", flush=True)
        return 0

    import psycopg
    start_of_day = datetime.combine(day, time.min, tzinfo=NEW_YORK)
    with psycopg.connect(db_url, connect_timeout=10, autocommit=True) as conn:
        try:
            restored = reconcile_completed_ai_snapshots(conn, day)
            if restored:
                print("[news-ai] restored_completed_snapshots count=%s" % len(restored), flush=True)
        except Exception as exc:
            # Recovery is independent of today's candidate selection.
            print("[news-ai] reconcile_failed category=%s" % type(exc).__name__, flush=True)
        with conn.cursor() as cur:
            cur.execute(
                """SELECT s.stock_name, s.result_limit, s.storyboard_limit,
                          s.display_timezone, s.source_fingerprint, s.result_payload
                   FROM public.news_processed_snapshots s
                   WHERE s.market='미국'
                     AND s.stock_name=ANY(%s)
                     AND s.expires_at > now()
                     AND s.processed_at >= %s
                     AND CASE WHEN jsonb_typeof(s.result_payload->'paired_news_items')='array'
                              THEN jsonb_array_length(s.result_payload->'paired_news_items') ELSE 0 END > 0
                     AND EXISTS (
                         SELECT 1
                         FROM jsonb_array_elements(s.result_payload->'paired_news_items') a
                         WHERE length(btrim(COALESCE(a->>'title',''))) > 0
                           AND length(btrim(COALESCE(a->>'description', a->>'body',''))) > 0
                           AND length(btrim(COALESCE(a->>'published_at', a->>'pubDate',''))) > 0
                     )
                     AND NOT EXISTS (
                         SELECT 1 FROM public.news_ai_call_ledger l
                         WHERE l.market='US' AND l.symbol=s.stock_name
                           AND l.exchange_day=%s
                     )
                   ORDER BY s.processed_at DESC
                   LIMIT 2""",
                (list(APPROVED_US), start_of_day, day),
            )
            candidates = cur.fetchall()
        done = 0
        for stock_name, result_limit, storyboard_limit, tz, fingerprint, payload in candidates:
            articles = payload.get("paired_news_items") or []
            if not has_eligible_ai_news(articles):
                print("[news-ai] scheduled skipped reason=no_dated_usable_article stock=%s" % stock_name, flush=True)
                continue
            outcome = run_stock_batch(conn, [{
                "market": "US", "symbol": stock_name, "name": stock_name,
                "exchange_day": day, "articles": articles,
            }])[0]
            print("[news-ai] scheduled stock=%s status=%s count=%s" % (
                stock_name, outcome["status"], outcome.get("issue_count", 0)), flush=True)
            if outcome["status"] != "ok":
                continue
            done += 1
            ids = outcome.get("ids") or []
            sources = outcome.get("issue_sources") or []
            if not ids:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT headline, summary, tags
                       FROM public.news_ai_issues WHERE id=ANY(%s) ORDER BY id""",
                    (ids,),
                )
                issues = [{"headline": h, "summary": s, "tags": tags}
                          for h, s, tags in cur.fetchall()]
            if not issues:
                continue
            display_time = datetime.now(SEOUL).strftime("%Y-%m-%d %H:%M")
            updated = with_ai_issue_briefs(
                payload, issues, display_time=display_time, stock_names=[stock_name],
                sources_by_issue=sources, exchange_day=day)
            # Patch only AI and preserved-code fields.  Never replace newer
            # articles with an older snapshot if news refreshes during Groq.
            ai_json = json.dumps(updated["_ai_issue_briefs"], ensure_ascii=False)
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE public.news_processed_snapshots
                       SET result_payload = jsonb_set(
                           jsonb_set(
                               jsonb_set(result_payload,
                                   '{_code_issue_briefs}',
                                   COALESCE(result_payload->'_code_issue_briefs',
                                            result_payload->'issue_briefs','[]'::jsonb),true),
                               '{_ai_issue_briefs}',%s::jsonb,true),
                           '{issue_briefs}',%s::jsonb,true)
                           || jsonb_build_object('_ai_exchange_day',%s)
                       WHERE market='미국' AND stock_name=%s
                         AND result_limit=%s AND storyboard_limit=%s
                         AND display_timezone=%s
                         AND expires_at>now()""",
                    (ai_json, ai_json, day.isoformat(), stock_name,
                     result_limit, storyboard_limit, tz),
                )
                updated_rows = cur.rowcount
            print("[news-ai] scheduled snapshot_updated stock=%s rows=%s" % (
                stock_name, updated_rows), flush=True)
        return done
