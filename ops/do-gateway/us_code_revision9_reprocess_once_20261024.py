"""One-time, AI-free US code/news refresh through the existing DO gateway.

Read only the current US snapshot keys and recompute them using the already
deployed verified-original-body rev9 code. Never invoke Groq, delete news,
consolidate share classes, or rewrite another stock's snapshot.
"""
from __future__ import annotations

import os
import time
import sys
from datetime import datetime
# Gateway executes a /run/gaemi-gateway/job-*.py copy under the app CWD.
# Make the project import root explicit without touching production PYTHONPATH.
sys.path.insert(0, "/opt/gaemigtp-news/app")

from backend.services import news_feed, news_processed_store as store
from backend.services.news_result import (
    _us_source_first_three_sentences,
    build_stock_news_result,
)

EXPECTED_REVISION = 9
DEADLINE_SECONDS = 780
RESULT_LIMIT = 50
STORYBOARD_LIMIT = 3
DISPLAY_TIMEZONE = "Asia/Seoul"
PRIORITY = (
    "엔비디아", "테슬라", "AMD", "메타", "알파벳 A",
    "스페이스X", "애플", "마이크론 테크놀로지", "모더나",
    "SK하이닉스 ADR", "SK하이닉스(ADR)", "TSMC ADR",
    "팔란티어 테크", "알파벳 C",
)


def _targets():
    with store._connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT stock_name, COALESCE(result_payload->>'_code_source_revision', '')
                FROM public.news_processed_snapshots
                WHERE market='미국' AND expires_at>now()
                ORDER BY stock_name
            """)
            rows = cur.fetchall()
    order = {name: index for index, name in enumerate(PRIORITY)}
    return sorted(rows, key=lambda row: (
        1 if row[1] == str(EXPECTED_REVISION) else 0,
        order.get(row[0], 100),
        row[0],
    ))


def _reprocess(name):
    params = {
        "market": "미국", "limit": RESULT_LIMIT,
        "storyboard_limit": STORYBOARD_LIMIT,
        "display_timezone": DISPLAY_TIMEZONE,
    }
    raw = news_feed.fetch_stock_news(
        name, market="미국", limit=RESULT_LIMIT, raise_on_error=True,
    )
    if not raw:
        return "no_source_news", 0, 0
    fingerprint = store.source_fingerprint(raw)
    if store.read_signature(name, **params) == fingerprint:
        return "already_fresh", len(raw), 0
    result = build_stock_news_result(name, raw_news_list=raw, **params)
    if result.get("_news_status") != "ok":
        return "analysis_failed_old_preserved", len(raw), 0
    if result.get("_code_source_revision") != EXPECTED_REVISION:
        raise RuntimeError("code_revision_mismatch")
    issues = result.get("issue_briefs") or []
    for brief in issues:
        if not isinstance(brief, dict) or (
            brief.get("evidence_source") != "verified_article_body_title_only"
            or not brief.get("source_articles")
            or not brief.get("summary")
            or _us_source_first_three_sentences(brief["summary"]) != brief["summary"]
        ):
            raise RuntimeError("unverified_or_overlong_code_issue_blocked")
        for source in brief["source_articles"]:
            if not str(source.get("url") or "").startswith(("https://", "http://")):
                raise RuntimeError("invalid_source_url")
            try:
                published = datetime.fromisoformat(
                    str(source.get("published_at") or "").replace("Z", "+00:00"))
            except (TypeError, ValueError) as exc:
                raise RuntimeError("invalid_source_date") from exc
            if published.utcoffset() is None:
                raise RuntimeError("naive_source_date")
    store.save_snapshot(name, fingerprint=fingerprint, result=result, **params)
    # Deliberately no AI runner, Groq model calls or AI reservations.
    return "reprocessed", len(raw), len(issues)


def main():
    if not store.database_url():
        raise SystemExit("NEWS_DATABASE_URL_not_loaded")
    # Defence in depth; we never import the live AI runner anyway.
    os.environ["GAEMIGTP_NEWS_WORKER"] = "1"
    os.environ["GAEMIGTP_NEWS_AI_PAUSED"] = "1"
    started = time.monotonic()
    deadline = started + DEADLINE_SECONDS
    targets = _targets()
    results = {}
    print("US_REV9_REFRESH_START targets=%d paid_ai_calls=0" % len(targets), flush=True)
    for index, (name, version) in enumerate(targets, start=1):
        if time.monotonic() >= deadline - 30:
            print("US_REV9_REFRESH_DEADLINE_REACHED remaining=%d" % (len(targets)-index+1),flush=True)
            break
        t = time.monotonic()
        try:
            status, fetched, issues = _reprocess(name)
        except Exception as exc:
            status, fetched, issues = "error_"+type(exc).__name__, 0, 0
            print("US_REV9_REFRESH_ERROR stock=%s code=%s" % (
                name, type(exc).__name__), flush=True)
        results[status] = results.get(status, 0) + 1
        print("US_REV9_REFRESH_ITEM index=%d stock=%s prevrev=%s status=%s news=%d code_issues=%d seconds=%.1f" % (
            index,name,version or "legacy",status,fetched,issues,time.monotonic()-t
        ),flush=True)
    with store._connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*),
                       COUNT(*) FILTER(WHERE result_payload->>'_code_source_revision'='7'),
                       COUNT(*) FILTER(WHERE result_payload->>'_code_source_revision' IS DISTINCT FROM '7'),
                       SUM(jsonb_array_length(
                           CASE WHEN jsonb_typeof(result_payload->'_code_issue_briefs')='array'
                           THEN result_payload->'_code_issue_briefs' ELSE '[]'::jsonb END
                       ))
                FROM public.news_processed_snapshots WHERE market='미국' AND expires_at>now()
            """)
            total, rev9, legacy, code_issues = cur.fetchone()
    print("US_REV9_REFRESH_SUMMARY total=%d rev9=%d older=%d code_issues=%d statuses=%r paid_ai_calls=0 seconds=%.1f" % (
        total,rev9,legacy,code_issues,results,time.monotonic()-started
    ),flush=True)
    if results.get("reprocessed",0)==0 and rev9 < total:
        raise SystemExit("US_REV9_REFRESH_NO_PROGRESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
