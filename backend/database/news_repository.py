"""Best-effort asynchronous storage of news metadata in shared Neon Postgres.

No news scraping, article-body storage, or API exposure happens here.
The existing news UI must not wait for database writes.
"""
import logging
import os
import queue
import threading
import urllib.parse

_QUEUE = queue.Queue(maxsize=200)
_STARTED = False
_LOCK = threading.Lock()
_LOG = logging.getLogger(__name__)

_CATEGORY_MAP = {
    "물가·경제지표": "macro", "금리·통화정책": "macro",
    "실적발표": "earnings", "정책·규제": "policy",
    "반도체 업황": "semiconductor", "AI 투자": "ai",
    "유가·에너지": "energy", "공급망": "supply_chain",
    "반도체": "semiconductor", "AI·소프트웨어": "ai",
    "에너지": "energy", "바이오·헬스케어": "biotech",
}

def _source(row):
    url = str(row.get("url") or row.get("link") or "")
    host = urllib.parse.urlsplit(url).hostname or ""
    if host.startswith("www."):
        host = host[4:]
    kind = str(row.get("source_type") or "")
    if kind == "sec_filing":
        return "sec", "공시", "filing"
    if kind == "official_company":
        return "official:" + host, "기업 공식", "company"
    return "news:" + host, str(row.get("source") or host or "뉴스"), "news"

def _write_batch(stock, market, articles):
    import psycopg
    from psycopg.types.json import Jsonb
    dsn = os.environ["NEWS_DATABASE_URL"]
    from backend.analysis.news.catalog import STOCK_UNIVERSE
    region = ("US" if str(market).lower() in ("us", "미국") or
              (not market and stock in STOCK_UNIVERSE.get("미국", {})) else "KR")
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            for row in articles:
                url = str(row.get("url") or row.get("link") or "").strip()
                title = str(row.get("title") or "").strip()
                if not url.startswith(("https://", "http://")) or not title:
                    continue
                from .news_url import canonical_news_url, news_url_hash
                canonical = canonical_news_url(url)
                digest = news_url_hash(url)
                if not digest:
                    continue
                key, display, kind = _source(row)
                cur.execute(
                    "INSERT INTO news_sources(source_key,display_name,source_type) VALUES (%s,%s,%s) "
                    "ON CONFLICT(source_key) DO UPDATE SET display_name=EXCLUDED.display_name "
                    "RETURNING id", (key, display, kind))
                source_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO news_articles(source_id,canonical_url,url_hash,headline,excerpt,"
                    "publisher,published_at,source_payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT(url_hash) DO UPDATE SET updated_at=now(), "
                    "headline=EXCLUDED.headline,excerpt=EXCLUDED.excerpt "
                    "RETURNING id",
                    (source_id, canonical, digest, title, str(row.get("description") or "")[:1200],
                     display, row.get("published_at") or None,
                     Jsonb({"origin": kind, "source_type": str(row.get("source_type") or "")})))
                article_id = cur.fetchone()[0]
                aliases = STOCK_UNIVERSE.get("미국", {}).get(stock, []) if region == "US" else []
                canonical_us = next((x for x in aliases if x.isascii() and x.upper() == x and len(x) <= 8), "")
                symbol = str(row.get("symbol") or canonical_us or stock).strip()
                if symbol:
                    cur.execute(
                        "INSERT INTO news_article_symbols(article_id,market,symbol,relevance) "
                        "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (article_id, region, symbol, "direct" if int(row.get("analysis_relevance_tier") or 0) >= 3 else "related"))
                for category in set(str(x) for x in
                                    (list(row.get("issues") or []) + list(row.get("themes") or []))):
                    category_key = _CATEGORY_MAP.get(category)
                    if category_key:
                        cur.execute(
                            "INSERT INTO news_article_categories(article_id,category_key,method) "
                            "VALUES (%s,%s,'rule') ON CONFLICT DO NOTHING",
                            (article_id, category_key))

def _worker():
    while True:
        stock, market, articles = _QUEUE.get()
        try:
            _write_batch(stock, market, articles)
            # Cleanup is independent of ingestion and runs only for
            # expired sources with durable, verified processing evidence.
            from .news_retention import cleanup_once_per_day
            cleanup_once_per_day()
        except Exception as exc:
            _LOG.warning("news metadata persistence skipped: %s", type(exc).__name__)
        finally:
            _QUEUE.task_done()

def enqueue_news_metadata(stock, market, articles):
    """Do not enqueue unless durable DB configured; never block response."""
    global _STARTED
    if os.environ.get("NEWS_METADATA_STORAGE_ENABLED") != "1" or not os.environ.get("NEWS_DATABASE_URL"):
        return
    with _LOCK:
        if not _STARTED:
            threading.Thread(target=_worker, name="news-metadata-writer", daemon=True).start()
            _STARTED = True
    try:
        _QUEUE.put_nowait((stock, market, list(articles)))
    except queue.Full:
        _LOG.warning("news metadata queue full; skipping a batch")
