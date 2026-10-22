"""Store Alpaca news and its exact Neon instrument links (DigitalOcean only).

Use existing market_instruments + news_article_symbols; never create a second
ticker catalog or guess a ticker from an article headline.
"""
import datetime
import hashlib
import json
import os
import re
import urllib.parse

from backend.analysis.news.stock_identity import normalize_us_ticker


def save_stock_articles(ticker, items):
    """Attach confirmed API-tagged articles to existing US instrument symbols."""
    if os.getenv("GAEMIGTP_NEWS_WORKER") != "1":
        return 0
    database_url = os.getenv("NEWS_DATABASE_URL", "").strip()
    ticker = normalize_us_ticker(ticker)
    if not database_url or not ticker or not items:
        return 0
    try:
        import psycopg
        now = datetime.datetime.now(datetime.timezone.utc)
        with psycopg.connect(database_url, connect_timeout=4) as conn:
            with conn.cursor() as cur:
                # Use the *existing* Neon identity registry and preserve
                # exchange-specific symbols (NVDA.O -> NVDA).
                cur.execute(
                    """SELECT symbol FROM public.market_instruments
                       WHERE market='US' AND is_active=true
                         AND regexp_replace(upper(symbol), '\\.(O|N|K)$', '') = %s""",
                    (ticker,),
                )
                symbols = [row[0] for row in cur.fetchall()]
                if not symbols:
                    return 0  # Unknown instruments are never invented.
                cur.execute(
                    """INSERT INTO public.news_sources
                       (source_key, display_name, source_type, homepage_url)
                       VALUES ('alpaca','Alpaca (Benzinga)','news','https://www.alpaca.markets')
                       ON CONFLICT (source_key) DO NOTHING"""
                )
                saved = 0
                for item in items:
                    tagged = {normalize_us_ticker(s) for s in (item.get("provider_symbols") or [])}
                    if ticker not in tagged:
                        continue
                    title = str(item.get("title") or "").strip()
                    url = str(item.get("url") or "").strip()
                    parsed = urllib.parse.urlsplit(url)
                    if not title or parsed.scheme not in ("https", "http") or not parsed.netloc:
                        continue
                    try:
                        published = datetime.datetime.fromisoformat(
                            str(item.get("published_at") or "").replace("Z", "+00:00")
                        )
                        if published.tzinfo is None or published.utcoffset() is None:
                            continue
                        published = published.astimezone(datetime.timezone.utc)
                    except (TypeError, ValueError):
                        continue
                    if not now - datetime.timedelta(hours=24) <= published <= now:
                        continue
                    excerpt = str(item.get("description") or "")[:1800]
                    source_payload = json.dumps({
                        "provider": "alpaca",
                        "symbols": sorted(tagged),
                        "source": str(item.get("source") or "")[:100],
                    }, ensure_ascii=False)
                    cur.execute(
                        """INSERT INTO public.news_articles
                           (source_id, canonical_url, url_hash, headline, excerpt,
                            language, publisher, published_at, source_payload,
                            body_storage_policy, processing_status,
                            retention_expires_at)
                           VALUES (
                             (SELECT id FROM public.news_sources WHERE source_key='alpaca'),
                             %s,%s,%s,%s,'en',%s,%s,%s::jsonb,
                             'metadata_only','pending',%s
                           )
                           ON CONFLICT (url_hash) DO UPDATE
                           SET updated_at=now(),
                               excerpt=COALESCE(public.news_articles.excerpt, EXCLUDED.excerpt)
                           RETURNING id""",
                        (url, hashlib.sha256(url.encode()).hexdigest(),
                         title, excerpt, str(item.get("source") or "")[:100],
                         published, source_payload,
                         published + datetime.timedelta(hours=24)),
                    )
                    article_id = cur.fetchone()[0]
                    for db_symbol in symbols:
                        cur.execute(
                            """INSERT INTO public.news_article_symbols
                               (article_id,market,symbol,relevance)
                               VALUES (%s,'US',%s,'direct')
                               ON CONFLICT (article_id,market,symbol)
                               DO UPDATE SET relevance='direct'""",
                            (article_id, db_symbol),
                        )
                    saved += 1
        return saved
    except Exception as exc:
        print("[alpaca-neon] save_failed type=" + type(exc).__name__, flush=True)
        return 0
