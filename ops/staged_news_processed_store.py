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
                SELECT source_fingerprint, result_payload FROM public.news_processed_snapshots
                WHERE market=%s AND stock_name=%s AND result_limit=%s
                AND storyboard_limit=%s AND display_timezone=%s
                AND expires_at>now() LIMIT 1
            """, (market, stock_name, limit, storyboard_limit, display_timezone))
            row = cur.fetchone()
            if not row:
                return None
            payload = row[1] if isinstance(row[1], dict) else {}
            if market in ("미국", "US") and (
                payload.get("_title_only_revision") != 3
                or payload.get("_kr_selection_revision") != 1
                or payload.get("_code_source_revision") != 20
                or payload.get("_company_match_revision") != 2
                or payload.get("_event_taxonomy_revision") != 1
                or payload.get("_issue_selection_revision") != 2
                or (payload.get("_translation_enabled") and payload.get("_translation_pending_count", 0) > 0)
            ):
                # Reprocess older code-only snapshots once without touching AI.
                return None
            briefs = payload.get("issue_briefs") or []
            if len(_same_stock_issue_briefs(briefs, stock_name)) != len(briefs):
                # Re-evaluate legacy mismatched issues one time; save_snapshot
                # sanitizes the replacement even when source news is unchanged.
                return None
            return row[0]

def read_snapshot(stock_name, *, market, limit=50, storyboard_limit=3,
                  display_timezone="Asia/Seoul"):
    """US results remain readable until expiry; retain the KR worker health check."""
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
                    AND (market IN ('미국', 'US', 'us')
                         OR checked_at > now() - interval '20 minutes')
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


def _same_stock_issue_briefs(briefs, stock_name):
    """Accept only the same verified company, not a similarly named competitor."""
    from backend.analysis.news.catalog import canonical_us_news_name
    canonical = canonical_us_news_name(stock_name)
    return [
        brief for brief in (briefs or [])
        if isinstance(brief, dict)
        and (
            stock_name in (brief.get("stock_names") or [])
            or (canonical != stock_name and any(
                canonical_us_news_name(name) == canonical
                for name in (brief.get("stock_names") or [])
                if isinstance(name, str)
            ))
        )
    ]


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
        if not _same_stock_issue_briefs([item], stock_name):
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


def _fresh_ai_briefs(briefs, *, now=None):
    """Display only AI issues with genuine source links published within 24h."""
    from datetime import datetime, timezone, timedelta
    from email.utils import parsedate_to_datetime
    from urllib.parse import urlparse
    from zoneinfo import ZoneInfo

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    valid = []
    for brief in briefs or []:
        if not isinstance(brief, dict):
            continue
        if brief.get("_issue_expires_at"):
            try:
                expiry = datetime.fromisoformat(str(brief["_issue_expires_at"]).replace("Z", "+00:00"))
                if expiry.tzinfo is None or expiry <= now:
                    continue
            except (ValueError, TypeError):
                continue
        recent_sources = []
        for source in (brief.get("source_articles") or []):
            if not isinstance(source, dict):
                continue
            url = str(source.get("url") or "").strip()
            if not url.startswith(("https://", "http://")):
                continue
            stamp = str(source.get("published_at") or "").strip()
            try:
                published = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                try:
                    published = parsedate_to_datetime(stamp)
                except (TypeError, ValueError, IndexError):
                    continue
            if published.tzinfo is None or not cutoff <= published.astimezone(timezone.utc) <= now:
                continue
            publisher = str(source.get("source") or "").strip()
            if not publisher:
                publisher = urlparse(url).hostname or ""
            if not publisher:
                continue
            recent_sources.append((published, {**source, "source": publisher}))
        if recent_sources:
            latest = max(recent_sources, key=lambda pair: pair[0])[0]
            valid.append({
                **brief,
                "time": latest.astimezone(ZoneInfo("Asia/Seoul")).strftime("%H:%M"),
                "reaction_at": "",
                "source_articles": [item for _, item in recent_sources],
            })
    return valid


def _prefer_same_day_ai(coming, previous, stock_name, us_day):
    """Keep same-stock, source-fresh AI across US day boundaries, until 24h expiry."""
    code = _same_stock_issue_briefs(
        coming.get("_code_issue_briefs", coming.get("issue_briefs") or []), stock_name)
    if (not code and isinstance(previous, dict)
            and previous.get("_code_source_revision") == 20
            and previous.get("_company_match_revision") == 2
            and previous.get("_issue_selection_revision") == 2):
        # Preserve only this company's still-dated, source-backed code issues.
        # Never use issue_briefs here: that field may contain the AI channel.
        prior_code = _same_stock_issue_briefs(
            previous.get("_code_issue_briefs") or [], stock_name)
        code = _fresh_ai_briefs(prior_code)
    coming["_code_issue_briefs"] = code
    candidate = []
    candidate_day = None
    if coming.get("_ai_exchange_day") == us_day:
        incoming = coming.get("_ai_issue_briefs") or []
        candidate = _fresh_ai_briefs(_same_stock_issue_briefs(incoming, stock_name))
        if len(candidate) != len(incoming):
            candidate = []
        if candidate:
            candidate_day = us_day
    # A news refresh can happen after NY midnight, while yesterday's article
    # is still less than 24 hours old. Preserve that verified analysis without
    # relabeling it as a new AI call today.
    if not candidate and isinstance(previous, dict):
        previous_day = previous.get("_ai_exchange_day")
        if isinstance(previous_day, str) and previous_day <= us_day:
            prior = previous.get("_ai_issue_briefs") or []
            candidate = _fresh_ai_briefs(_same_stock_issue_briefs(prior, stock_name))
            if candidate:
                candidate_day = previous_day
    if candidate:
        coming["_ai_issue_briefs"] = candidate
        coming["_ai_exchange_day"] = candidate_day
        coming["issue_briefs"] = candidate
    else:
        coming.pop("_ai_issue_briefs", None)
        coming.pop("_ai_exchange_day", None)
        coming["issue_briefs"] = []
    return coming


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
    valid = _same_stock_issue_briefs(submitted, stock_name)
    if len(valid) != len(submitted):
        print(
            f"[news-worker] unrelated_issues_rejected stock={stock_name} count={len(submitted)-len(valid)}",
            flush=True,
        )
    normalized["issue_briefs"] = valid
    with _connect() as conn:
        with conn.cursor() as cur:
            # Keep AI and deterministic issue channels separate without
            # altering news collection, retention, or existing read APIs.
            previous_payload = None
            if market in ("미국", "US") or not normalized.get("issue_briefs"):
                cur.execute("""
                    SELECT result_payload FROM public.news_processed_snapshots
                    WHERE market=%s AND stock_name=%s AND result_limit=%s
                    AND storyboard_limit=%s AND display_timezone=%s
                    AND expires_at>now()
                    FOR UPDATE
                """, (market, stock_name, limit, storyboard_limit, display_timezone))
                previous = cur.fetchone()
                previous_payload = previous[0] if previous else None
            if market in ("미국", "US"):
                from datetime import datetime
                from zoneinfo import ZoneInfo
                day = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
                normalized = _prefer_same_day_ai(normalized, previous_payload,
                                                  stock_name, day)
            # US display is AI-only; never resurrect legacy code headlines.
            if market not in ("미국", "US") and not normalized.get("issue_briefs"):
                preserved = _recent_existing_issue_briefs(previous_payload, stock_name)
                if preserved:
                    normalized["issue_briefs"] = preserved
                    if market in ("미국", "US"):
                        normalized["_code_issue_briefs"] = preserved
                    print(
                        f"[news-worker] preserved_recent_issues stock={stock_name} count={len(preserved)}",
                        flush=True,
                    )
            # KR only: replace grounded hashtag labels, never titles, summaries or news.
            if market in ("국내", "KR"):
                try:
                    from staged_issue_tags_only import tags_only
                    normalized, tag_count = tags_only(normalized, stock_name)
                    if tag_count:
                        print(f"[news-worker] kr_tag_only_changed stock={stock_name} count={tag_count}", flush=True)
                except Exception as exc:
                    print(f"[news-worker] kr_tag_overlay_skipped error={type(exc).__name__}", flush=True)
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

def _retained_24h_issue_briefs(briefs, *, now):
    """Only retain event briefs backed by a source from the past 24 hours."""
    from datetime import datetime, timezone, timedelta
    from email.utils import parsedate_to_datetime

    def parse(value):
        if not value:
            return None
        try:
            value = str(value)
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                dt = parsedate_to_datetime(value)
            return dt.astimezone(timezone.utc) if dt.tzinfo else None
        except (TypeError, ValueError, OverflowError, IndexError):
            return None

    lower = now - timedelta(hours=24)
    retained = []
    for brief in briefs or []:
        if not isinstance(brief, dict):
            continue
        expiry = parse(brief.get("_issue_expires_at"))
        if brief.get("_issue_expires_at") and (expiry is None or expiry <= now):
            continue
        sources = brief.get("source_articles") or []
        if not isinstance(sources, list):
            continue
        current_sources = [
            source for source in sources
            if isinstance(source, dict)
            and (lambda published: published is not None and lower < published <= now)(
                parse(source.get("published_at"))
            )
        ]
        if not current_sources:
            continue
        # Preserve original issue metadata while removing expired source details.
        result = dict(brief)
        result["source_articles"] = current_sources
        retained.append(result)
    return retained


def purge_expired():
    """Permanently purge 24h-expired CODE and AI issues without touching market feeds."""
    from datetime import datetime, timezone
    from psycopg.types.json import Jsonb

    now = datetime.now(timezone.utc)
    counters = {"snapshots": 0, "code": 0, "ai": 0, "legacy_results": 0,
                "legacy_ai": 0, "ai_archive": 0}
    with _connect() as conn:
        with conn.cursor() as cur:
            # Lock each snapshot row. Do not extend the snapshot's own expiration
            # or interfere with source fingerprints and worker refresh cadence.
            cur.execute("""
                SELECT market, stock_name, result_limit, storyboard_limit,
                       display_timezone, result_payload
                FROM public.news_processed_snapshots
                WHERE expires_at > now() AND market IN ('미국', 'US', 'us')
                FOR UPDATE
            """)
            for market, stock_name, limit, storyboard_limit, tz, payload in cur.fetchall():
                if not isinstance(payload, dict):
                    continue
                changes = {}
                for key, kind in (("_code_issue_briefs", "code"),
                                  ("_ai_issue_briefs", "ai"),
                                  ("issue_briefs", None)):
                    items = payload.get(key)
                    if not isinstance(items, list):
                        continue
                    retained = _retained_24h_issue_briefs(items, now=now)
                    if retained != items:
                        changes[key] = retained
                        if kind:
                            counters[kind] += len(items) - len(retained)
                if changes:
                    updated = dict(payload)
                    updated.update(changes)
                    cur.execute("""
                        UPDATE public.news_processed_snapshots
                        SET result_payload=%s
                        WHERE market=%s AND stock_name=%s AND result_limit=%s
                          AND storyboard_limit=%s AND display_timezone=%s
                    """, (Jsonb(updated), market, stock_name, limit, storyboard_limit, tz))

            # Independent AI/result storage has no snapshot-scoped expiration.
            cur.execute("DELETE FROM public.news_ai_issues WHERE generated_at <= now() - interval '24 hours'")
            counters["legacy_ai"] = cur.rowcount
            cur.execute("DELETE FROM public.news_processed_results_24h WHERE expires_at <= now()")
            counters["legacy_results"] = cur.rowcount
            cur.execute("DELETE FROM public.us_news_ai_archive_20261024 WHERE expires_at <= now()")
            counters["ai_archive"] = cur.rowcount
            cur.execute("DELETE FROM public.news_processed_snapshots WHERE expires_at <= now()")
            counters["snapshots"] = cur.rowcount
    print("[news-worker] 24h_issue_db_cleanup=" + json.dumps(counters, sort_keys=True), flush=True)
    return counters["snapshots"]
