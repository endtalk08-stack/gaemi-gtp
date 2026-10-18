"""Read stored AI issues from Neon for display; never generate or write issues on Render."""
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo


def read_ai_issue_briefs(market, names, *, max_per_stock=3):
    """Read the latest successful AI issue batch for each stock from Neon.

    This display read is independent of the 24-hour raw-news snapshot TTL.
    Older issues remain until the next successful AI generation replaces them.
    """
    if market not in ("us", "미국") or not names:
        return {}
    names = list(dict.fromkeys(str(name).strip() for name in names if str(name).strip()))
    database_url = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not database_url or not names:
        return {}
    try:
        import psycopg
        with psycopg.connect(database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH latest AS (
                        SELECT symbol, MAX(exchange_day) AS exchange_day
                        FROM public.news_ai_issues
                        WHERE market='US' AND symbol = ANY(%s) AND generated_at <= now()
                        GROUP BY symbol
                    )
                    SELECT i.symbol, i.headline, i.summary, i.tags, i.generated_at,
                           article.brief->>'time' AS article_clock,
                           article.brief->'source_articles'->0->>'published_at' AS article_published_at
                    FROM public.news_ai_issues AS i
                    JOIN latest ON latest.symbol = i.symbol
                               AND latest.exchange_day = i.exchange_day
                    LEFT JOIN LATERAL (
                        SELECT b.brief
                        FROM public.news_processed_snapshots AS snapshot
                        CROSS JOIN LATERAL jsonb_array_elements(
                            COALESCE(snapshot.result_payload->'issue_briefs', '[]'::jsonb)
                        ) AS b(brief)
                        WHERE snapshot.market='미국' AND snapshot.stock_name=i.symbol
                          AND snapshot.expires_at>now()
                          AND b.brief->>'headline'=i.headline
                        ORDER BY snapshot.expires_at DESC LIMIT 1
                    ) AS article ON TRUE
                    WHERE i.market='US' AND i.generated_at <= now()
                    ORDER BY i.generated_at DESC, i.id DESC
                    """,
                    (names,),
                )
                rows = cur.fetchall()
        result = {}
        for symbol, headline, summary, tags, generated_at, article_clock, article_published_at in rows:
            if not str(headline or "").strip():
                continue
            briefs = result.setdefault(symbol, [])
            if len(briefs) >= max_per_stock:
                continue
            # The UI time is the source article's publication time, NOT the
            # time our AI wrote its issue. The two can be hours or days apart.
            stamp = str(article_clock or "").strip()
            if not re.fullmatch(r"(?:[01]\\d|2[0-3]):[0-5]\\d", stamp):
                stamp = ""
            if not stamp and article_published_at:
                try:
                    published = datetime.fromisoformat(str(article_published_at).replace("Z", "+00:00"))
                    if published.tzinfo is not None:
                        stamp = published.astimezone(ZoneInfo("Asia/Seoul")).strftime("%H:%M")
                except (ValueError, TypeError):
                    pass
            # Without a source timestamp, never mislabel AI generation as article publication.
            if not stamp:
                stamp = "기사시각 미확인"
            briefs.append({
                "headline": str(headline).strip(),
                "summary": str(summary or "").strip(),
                "tags": tags if isinstance(tags, list) else [],
                "time": stamp,
                "stock_names": [symbol],
                "source": "ai_issue",
                "generated_at": generated_at.isoformat() if isinstance(generated_at, datetime) else "",
                "published_at": str(article_published_at or ""),
            })
        return result
    except Exception as exc:
        print("[AI issues] database read unavailable: " + type(exc).__name__, flush=True)
        return None
