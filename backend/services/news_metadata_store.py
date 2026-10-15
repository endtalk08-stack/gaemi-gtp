"""Passive news metadata persistence. Never changes the calling news response."""
import datetime
import hashlib
import html
import json
import os
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="news-metadata-save")
_PENDING = threading.BoundedSemaphore(4)
_CACHE_SECONDS = 7 * 24 * 60 * 60
_RETENTION_DAYS = 7
_CLEANUP_INTERVAL_SECONDS = 3600
_last_cleanup = 0.0
_cleanup_lock = threading.Lock()
_cleanup_worker_lock = threading.Lock()
_cleanup_worker_started = False


def _clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))).strip()


def _timestamp(value):
    try:
        dt = parsedate_to_datetime(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except (ValueError, TypeError, IndexError):
        return None


def _cache_key(query, display, start):
    value = json.dumps([str(query), int(display), int(start)], ensure_ascii=False)
    return "gaemi:news:naver:v1:" + hashlib.sha256(value.encode()).hexdigest()



def _retained_news(existing, incoming, *, now=None):
    """Keep previous news and merge new news; drop items older than 7 days."""
    current = now or datetime.datetime.now(datetime.timezone.utc)
    cutoff = current - datetime.timedelta(days=_RETENTION_DAYS)
    combined = {}
    for row in list(existing or []) + list(incoming or []):
        if not isinstance(row, dict):
            continue
        url = str(row.get("originallink") or row.get("link") or "").strip()
        try:
            parts = urllib.parse.urlsplit(url)
        except ValueError:
            continue
        if parts.scheme not in {"https", "http"} or not parts.netloc:
            continue
        if not _clean(row.get("title")):
            continue
        published = _timestamp(row.get("pubDate"))
        first_seen = row.get("_news_first_seen")
        if not published and first_seen:
            try:
                published = datetime.datetime.fromisoformat(str(first_seen))
            except (TypeError, ValueError):
                published = None
        if published and published < cutoff:
            continue
        if published and published > current:
            continue
        previous = combined.get(url)
        first_seen_at = (
            (previous or {}).get("_news_first_seen")
            or first_seen
            or current.isoformat()
        )
        combined[url] = {**row, "_news_first_seen": first_seen_at}
    def sort_time(row):
        published = _timestamp(row.get("pubDate"))
        if published:
            return published
        try:
            value = datetime.datetime.fromisoformat(str(row.get("_news_first_seen") or ""))
            return value.astimezone(datetime.timezone.utc)
        except (ValueError, TypeError):
            return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

    return sorted(combined.values(), key=sort_time, reverse=True)[:300]




def read_cached_news(query, display, start):
    """Read previously collected news without asking the original provider.

    Redis is the fast path; Neon is the fallback. Both retain articles rather
    than replacing the visible list each time a fresh batch is collected.
    Returns [] when no storage is configured or no matching data exists.
    """
    key = _cache_key(query, display, start)
    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    redis_client = None
    if redis_url and redis_token:
        try:
            from upstash_redis import Redis
            redis_client = Redis(url=redis_url, token=redis_token)
            data = redis_client.get(key)
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, list):
                kept = _retained_news(data, [])
                if kept:
                    return kept[:max(20, min(int(display), 100))]
        except Exception as exc:
            print("[news metadata] redis_read_failed type=" + type(exc).__name__, flush=True)

    database_url = os.getenv("NEWS_DATABASE_URL", "").strip()
    if not database_url:
        return []
    try:
        import psycopg
        with psycopg.connect(database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.headline, a.excerpt, a.canonical_url, a.published_at,
                           a.collected_at
                    FROM public.news_articles AS a
                    JOIN public.news_sources AS s ON s.id=a.source_id
                    WHERE s.source_key='naver'
                      AND (
                          a.source_payload ->> 'query' = %s
                          OR COALESCE(a.source_payload -> 'queries', '[]'::jsonb) ? %s
                      )
                      AND a.retention_expires_at > now()
                    ORDER BY a.published_at DESC NULLS LAST, a.collected_at DESC
                    LIMIT %s
                """, (str(query), str(query), max(20, min(int(display), 100))))
                result = cur.fetchall()
        from email.utils import format_datetime
        rows = []
        for title, excerpt, url, published, collected in result:
            published_str = (
                format_datetime(published.astimezone(datetime.timezone.utc), usegmt=True)
                if published else ""
            )
            rows.append({
                "title": title, "description": excerpt or "", "link": url,
                "originallink": url, "pubDate": published_str,
                "_news_first_seen": collected.astimezone(datetime.timezone.utc).isoformat()
                if collected else "",
            })
        kept = _retained_news(rows, [])
        if kept and redis_client is not None:
            try:
                redis_client.set(key, json.dumps(kept, ensure_ascii=False), ex=_CACHE_SECONDS)
            except Exception as exc:
                print("[news metadata] redis_fill_failed type=" + type(exc).__name__, flush=True)
        return kept
    except Exception as exc:
        print("[news metadata] db_read_failed type=" + type(exc).__name__, flush=True)
        return []



def _expire(cur):
    """Permanently delete only expired Naver articles, never other news."""
    global _last_cleanup
    now = time.monotonic()
    with _cleanup_lock:
        if now - _last_cleanup < _CLEANUP_INTERVAL_SECONDS:
            return
        cur.execute("""
            DELETE FROM public.news_articles
            WHERE source_id IN (SELECT id FROM public.news_sources WHERE source_key = 'naver')
              AND retention_expires_at <= now()
        """)
        _last_cleanup = now



def _cleanup_loop():
    """Remove expired news hourly while the server worker is running."""
    while True:
        time.sleep(_CLEANUP_INTERVAL_SECONDS)
        database_url = os.getenv("NEWS_DATABASE_URL", "").strip()
        if not database_url:
            continue
        try:
            import psycopg
            with psycopg.connect(database_url, connect_timeout=4) as conn:
                with conn.cursor() as cur:
                    _expire(cur)
        except Exception as exc:
            print("[news metadata] cleanup_failed type=" + type(exc).__name__, flush=True)


def _start_cleanup_worker():
    global _cleanup_worker_started
    if not os.getenv("NEWS_DATABASE_URL", "").strip():
        return
    with _cleanup_worker_lock:
        if _cleanup_worker_started:
            return
        thread = threading.Thread(
            target=_cleanup_loop, name="news-expiry-cleanup", daemon=True,
        )
        thread.start()
        _cleanup_worker_started = True



def _save(rows, query, display, start):
    if not rows:
        return
    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if redis_url and redis_token:
        try:
            from upstash_redis import Redis
            client = Redis(url=redis_url, token=redis_token)
            key = _cache_key(query, display, start)
            existing = client.get(key)
            if isinstance(existing, str):
                try:
                    existing = json.loads(existing)
                except (TypeError, ValueError):
                    existing = []
            merged = _retained_news(existing if isinstance(existing, list) else [], rows)
            client.set(key, json.dumps(merged, ensure_ascii=False), ex=_CACHE_SECONDS)
        except Exception as exc:
            print("[news metadata] redis_write_failed type=" + type(exc).__name__, flush=True)

    database_url = os.getenv("NEWS_DATABASE_URL", "").strip()
    if not database_url:
        print("[news metadata] db_not_configured", flush=True)
        return
    try:
        import psycopg
        with psycopg.connect(database_url, connect_timeout=4) as conn:
            with conn.cursor() as cur:
                _expire(cur)
                cur.execute("""
                    INSERT INTO public.news_sources (id,source_key,display_name,source_type)
                    VALUES (nextval('public.news_sources_id_seq'),'naver','네이버 뉴스 검색','news')
                    ON CONFLICT (source_key) DO NOTHING
                """)
                for row in rows:
                    url = str(row.get("originallink") or row.get("link") or "").strip()
                    title = _clean(row.get("title"))
                    try:
                        parsed = urllib.parse.urlsplit(url)
                    except ValueError:
                        continue
                    if not title or parsed.scheme not in ("http", "https") or not parsed.netloc:
                        continue
                    published = _timestamp(row.get("pubDate"))
                    if published and (
                        published < datetime.datetime.now(datetime.timezone.utc)
                        - datetime.timedelta(days=_RETENTION_DAYS)
                    ):
                        continue
                    cur.execute("""
                        INSERT INTO public.news_articles
                            (id, source_id, canonical_url, url_hash, headline, excerpt,
                             language, publisher, published_at, source_payload,
                             body_storage_policy, processing_status, retention_expires_at)
                        VALUES (
                            nextval('public.news_articles_id_seq'),
                            (SELECT id FROM public.news_sources WHERE source_key='naver'),
                            %s,%s,%s,%s,'ko',%s,%s,%s::jsonb,'metadata_only','pending',
                            COALESCE(%s::timestamptz, now()) + interval '7 days'
                        )
                        ON CONFLICT (url_hash) DO UPDATE SET
                            headline=EXCLUDED.headline,excerpt=EXCLUDED.excerpt,
                            source_payload=jsonb_set(
                                news_articles.source_payload, '{queries}',
                                (
                                    SELECT jsonb_agg(DISTINCT query_text)
                                    FROM jsonb_array_elements_text(
                                        COALESCE(
                                            news_articles.source_payload->'queries',
                                            jsonb_build_array(news_articles.source_payload->>'query')
                                        ) || EXCLUDED.source_payload->'queries'
                                    ) AS matched(query_text)
                                )
                            ),
                            updated_at=now()
                    """, (
                        url, hashlib.sha256(url.encode()).hexdigest(), title,
                        _clean(row.get("description")), parsed.netloc, published,
                        json.dumps({"provider": "naver", "query": str(query),
                                    "queries": [str(query)]}, ensure_ascii=False),
                        published,
                    ))
        print("[news metadata] db_saved count=" + str(len(rows)), flush=True)
    except Exception as exc:
        print("[news metadata] db_write_failed type=" + type(exc).__name__, flush=True)


def save_async(rows, query, display, start):
    """Nonblocking and bounded. Dropped jobs never affect live news display."""
    if not rows or not (os.getenv("NEWS_DATABASE_URL") or os.getenv("UPSTASH_REDIS_REST_URL")):
        return
    _start_cleanup_worker()
    if not _PENDING.acquire(blocking=False):
        return
    snapshot = [dict(row) for row in rows if isinstance(row, dict)][:100]
    def job():
        try:
            _save(snapshot, query, display, start)
        finally:
            _PENDING.release()
    try:
        _POOL.submit(job)
    except RuntimeError:
        _PENDING.release()
