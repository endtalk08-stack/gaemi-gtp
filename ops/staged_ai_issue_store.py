"""Staged persistence through the existing Neon connection.

Caller passes the already-open worker connection. No new connection or API.
This does not update live snapshots until the worker integration is verified.
"""
import json
from staged_daily_groq_issues import issue_records


def save_ai_issues(conn, issues, *, market, symbol, exchange_day):
    rows = issue_records(issues, market=market, symbol=symbol, exchange_day=exchange_day)
    if not rows:
        return []
    if conn is None or not callable(getattr(conn, "transaction", None)):
        raise ValueError("Existing transactional Neon connection required")
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
    return saved
