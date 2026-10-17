"""Store AI issues and their cited article metadata in existing Neon tables.

AI and source records are written together in one transaction. No article body is
persisted. The citation bundle lives in the pre-existing 24-hour results table,
not in the long-lived once-per-day paid-call ledger.
"""
import json
from staged_daily_groq_issues import issue_records

SOURCES_RESULT_TYPE = "stock_ai_issue_sources_v1"


def _result_key(market, symbol, exchange_day):
    return json.dumps([market, symbol, exchange_day.isoformat()],
                      ensure_ascii=False, separators=(",", ":"))


def _article_metadata(source):
    """Whitelisted Naver/search metadata only; never store article full text."""
    if not isinstance(source, dict):
        raise ValueError("Invalid source article metadata")
    url = str(source.get("url") or "").strip()[:2048]
    return {
        "source_id": source.get("source_id") if type(source.get("source_id")) is int else None,
        "title": str(source.get("title") or "")[:300],
        "description": str(source.get("description") or "")[:1200],
        "published_at": str(source.get("published_at") or "")[:80],
        "source": str(source.get("source") or "")[:120],
        "url": url if url.startswith(("https://", "http://")) else "",
    }


def save_ai_issues(conn, issues, *, market, symbol, exchange_day,
                   sources_by_issue=None):
    """Persist issues and exact source links atomically, with a 24-hour TTL."""
    rows = issue_records(issues, market=market, symbol=symbol, exchange_day=exchange_day)
    if not rows:
        return []
    if conn is None or not callable(getattr(conn, "transaction", None)):
        raise ValueError("Existing transactional Neon connection required")
    if sources_by_issue is not None:
        if (not isinstance(sources_by_issue, list)
            or len(sources_by_issue) != len(rows)
            or any(not isinstance(sources, list) or not sources
                   for sources in sources_by_issue)):
            raise ValueError("Each AI issue requires its own real source articles")
        sources_by_issue = [[_article_metadata(s) for s in group[:3]]
                            for group in sources_by_issue]
        if any(not s["title"] or not s["published_at"]
               for group in sources_by_issue for s in group):
            raise ValueError("Missing source title or publication timestamp")

    saved = []
    with conn.transaction():
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """INSERT INTO public.news_ai_issues
                       (market, symbol, exchange_day, headline, summary, tags, model_id)
                       VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                       RETURNING id""",
                    (
                        row["market"], row["symbol"], row["exchange_day"],
                        row["headline"], row["summary"],
                        json.dumps(row["tags"], ensure_ascii=False), row["model_id"],
                    ),
                )
                saved.append(cur.fetchone()[0])

            if sources_by_issue is not None:
                bundle = {
                    "market": market,
                    "symbol": symbol,
                    "exchange_day": exchange_day.isoformat(),
                    "issues": [
                        {
                            "issue_id": issue_id,
                            "headline": row["headline"],
                            "summary": row["summary"],
                            "tags": row["tags"],
                            "source_articles": sources,
                        }
                        for issue_id, row, sources
                        in zip(saved, rows, sources_by_issue)
                    ],
                }
                cur.execute(
                    """INSERT INTO public.news_processed_results_24h
                       (result_type, result_key, result_payload, created_at, expires_at)
                       VALUES (%s, %s, %s::jsonb, now(), now() + interval '24 hours')
                       ON CONFLICT (result_type, result_key)
                       DO UPDATE SET result_payload=EXCLUDED.result_payload,
                                     created_at=EXCLUDED.created_at,
                                     expires_at=EXCLUDED.expires_at""",
                    (SOURCES_RESULT_TYPE, _result_key(market, symbol, exchange_day),
                     json.dumps(bundle, ensure_ascii=False)),
                )
                # Only purge our own expired temporary citation bundles.
                cur.execute(
                    """DELETE FROM public.news_processed_results_24h
                       WHERE result_type=%s AND expires_at<=now()""",
                    (SOURCES_RESULT_TYPE,),
                )
    return saved


def read_issue_sources(conn, *, market, symbol, exchange_day, issue_ids):
    """Read valid 24-hour metadata aligned to the persisted issue order."""
    if not issue_ids:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """SELECT result_payload FROM public.news_processed_results_24h
               WHERE result_type=%s AND result_key=%s AND expires_at>now()
               LIMIT 1""",
            (SOURCES_RESULT_TYPE, _result_key(market, symbol, exchange_day)),
        )
        row = cur.fetchone()
    payload = row[0] if row and isinstance(row[0], dict) else {}
    by_id = {
        item["issue_id"]: item.get("source_articles") or []
        for item in payload.get("issues", [])
        if isinstance(item, dict) and type(item.get("issue_id")) is int
    }
    return [by_id.get(issue_id, []) for issue_id in issue_ids]
