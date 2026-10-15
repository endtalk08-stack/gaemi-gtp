"""Passive news metadata persistence. Never changes the calling news response."""
import datetime
import hashlib
import html
import json
import os
import re
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="news-metadata-save")
_PENDING = threading.BoundedSemaphore(4)
_CACHE_SECONDS = 120


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


def _save(rows, query, display, start):
    if not rows:
        return
    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if redis_url and redis_token:
        try:
            from upstash_redis import Redis
            Redis(url=redis_url, token=redis_token).set(
                _cache_key(query, display, start),
                json.dumps(rows, ensure_ascii=False),
                ex=_CACHE_SECONDS,
            )
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
                    cur.execute("""
                        INSERT INTO public.news_articles
                            (id, source_id, canonical_url, url_hash, headline, excerpt,
                             language, publisher, published_at, source_payload,
                             body_storage_policy, processing_status)
                        VALUES (
                            nextval('public.news_articles_id_seq'),
                            (SELECT id FROM public.news_sources WHERE source_key='naver'),
                            %s,%s,%s,%s,'ko',%s,%s,%s::jsonb,'metadata_only','pending'
                        )
                        ON CONFLICT (url_hash) DO UPDATE SET
                            headline=EXCLUDED.headline,excerpt=EXCLUDED.excerpt,
                            updated_at=now()
                    """, (
                        url, hashlib.sha256(url.encode()).hexdigest(), title,
                        _clean(row.get("description")), parsed.netloc, published,
                        json.dumps({"provider": "naver", "query": str(query)}, ensure_ascii=False),
                    ))
        print("[news metadata] db_saved count=" + str(len(rows)), flush=True)
    except Exception as exc:
        print("[news metadata] db_write_failed type=" + type(exc).__name__, flush=True)


def save_async(rows, query, display, start):
    """Nonblocking and bounded. Dropped jobs never affect live news display."""
    if not rows or not (os.getenv("NEWS_DATABASE_URL") or os.getenv("UPSTASH_REDIS_REST_URL")):
        return
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
