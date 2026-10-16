#!/usr/bin/env python3
"""Read-only audit for US stock issue dropouts on the EXISTING news worker.

No calls to Naver/AI/Render, no database writes, no configuration changes.
Run with the worker's existing NEWS_DATABASE_URL in its environment.
Requires psycopg (already installed in the worker venv).

Usage:
  python ops/news-worker/audit-us-issue-dropout.py
  python ops/news-worker/audit-us-issue-dropout.py --stock 테슬라 --stock '마이크론 테크놀로지'
  python ops/news-worker/audit-us-issue-dropout.py --journal  # reads existing systemd logs if permitted

Prints only counts and rejection categories, not articles, URLs, secrets, or raw log lines.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

DEFAULT_STOCKS = ("테슬라", "마이크론 테크놀로지", "스페이스X", "코어위브", "인텔", "메타", "엔비디아")
JOURNAL_UNIT = "gaemigtp-news.service"

READ_ONLY_SQL = """
SELECT stock_name, processed_at, checked_at,
       result_payload->'paired_news_items',
       result_payload->'storyboard_news_items',
       result_payload->'issue_briefs',
       result_payload->>'_news_status'
FROM public.news_processed_snapshots
WHERE market='미국' AND stock_name = ANY(%s)
ORDER BY stock_name
"""


def _sequence(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    return value if isinstance(value, list) else []


def summarize_snapshot(row):
    stock, processed_at, checked_at, items, selected, briefs, status = row
    items = _sequence(items)
    relation_counts = collections.Counter(str(item.get("relation_type") or "unknown")
                                          for item in items if isinstance(item, dict))
    direct = [item for item in items
              if isinstance(item, dict) and item.get("relation_type") == "direct"]
    return {
        "stock": stock,
        "status": status,
        "news": len(items),
        "direct": len(direct),
        "direct_with_keyword": sum(bool(item.get("storyboard_keywords")) for item in direct),
        "mention_or_indirect": relation_counts["mention_only"] + relation_counts["indirect"],
        "selected": len(_sequence(selected)),
        "issues": len(_sequence(briefs)),
        "processed_at_utc": processed_at.isoformat() if processed_at else None,
        "checked_at_utc": checked_at.isoformat() if checked_at else None,
        "requires_rejection_trace": bool(direct and not _sequence(briefs)),
    }


def parse_rejection_counts(lines, wanted):
    """Accept only controlled diagnostic fields; never print arbitrary log text."""
    counts = collections.defaultdict(collections.Counter)
    expected = set(wanted)
    for line in lines:
        if "[news decision]" not in line:
            continue
        try:
            record = json.loads(line.partition("[news decision]")[2].strip())
        except (ValueError, TypeError):
            continue
        if not isinstance(record, dict):
            continue
        stock = str(record.get("stock", ""))
        if stock not in expected:
            continue
        stage = str(record.get("stage", ""))
        if stage == "rejected_after_body":
            reason = str(record.get("reason", "unknown"))
        elif stage == "rejected_before_body":
            reason = str(record.get("reason", "unknown"))
        elif stage == "accepted_after_body":
            reason = "body_accepted"
        elif stage == "selected_issue_article":
            reason = "article_selected"
        else:
            continue
        if not re.fullmatch(r"[a-z_]{1,64}", reason):
            reason = "other"
        counts[stock][stage + ":" + reason] += 1
    return {stock: dict(counts[stock]) for stock in wanted if stock in counts}


def read_recent_journal():
    # Do not invoke sudo or alter service state; missing permissions remain a diagnostic blocker.
    result = subprocess.run(
        ["journalctl", "-u", JOURNAL_UNIT, "--since", "24 hours ago",
         "--no-pager", "-o", "cat"],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if result.returncode:
        print("JOURNAL_UNAVAILABLE: read permissions or journal not available")
        return []
    return result.stdout.splitlines()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", action="append", default=[], help="US stock name in existing snapshots")
    parser.add_argument("--journal", action="store_true", help="Also count rejection categories already logged")
    args = parser.parse_args(argv)
    wanted = sorted(set(args.stock or DEFAULT_STOCKS))
    if not wanted or len(wanted) > 30:
        print("INVALID_STOCK_COUNT")
        return 2
    database_url = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not database_url:
        print("NEWS_DATABASE_URL_NOT_CONFIGURED")
        return 2
    try:
        import psycopg
        with psycopg.connect(database_url, connect_timeout=8) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(READ_ONLY_SQL, (wanted,))
                rows = cursor.fetchall()
    except Exception as exc:
        print("READ_ONLY_AUDIT_FAILED type=" + type(exc).__name__)
        return 1

    output = {row["stock"]: row for row in (summarize_snapshot(r) for r in rows)}
    for stock in wanted:
        print(json.dumps(output.get(stock, {"stock": stock, "snapshot": "missing"}),
                         ensure_ascii=False, separators=(",", ":")))
    if args.journal:
        existing = parse_rejection_counts(read_recent_journal(), wanted)
        for stock in wanted:
            print(json.dumps({"stock": stock, "rejection_trace": existing.get(stock, {}),
                              "trace_available": stock in existing},
                             ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
