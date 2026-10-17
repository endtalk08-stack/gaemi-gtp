"""Staged issue evidence snapshot; does not modify live DB or call AI.

Only URLs already verified against collected article rows are persisted.
The evidence table is independent of news_articles deletion.
"""
from urllib.parse import urlsplit


def persist_issue_evidence(conn, issue_id, article_ids):
    """Snapshot genuine collected URLs before the article retention cleanup.

    The caller must have independently verified each article supports the issue.
    An empty article list writes no evidence. Return inserted/updated row count.
    """
    if not isinstance(issue_id, int) or issue_id <= 0:
        raise ValueError("Invalid issue ID")
    if any(not isinstance(article_id, int) or article_id <= 0 for article_id in article_ids):
        raise ValueError("Invalid article ID")
    article_ids = list(dict.fromkeys(article_ids))
    if not article_ids:
        return 0

    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, url_hash, canonical_url, headline, publisher
               FROM public.news_articles
               WHERE id = ANY(%s)""",
            (article_ids,),
        )
        articles = cur.fetchall()
        if len(articles) != len(article_ids):
            raise ValueError("One or more article IDs do not exist")
        for article_id, url_hash, canonical_url, headline, publisher in articles:
            parsed = urlsplit(canonical_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or not url_hash:
                raise ValueError("Invalid collected article URL")
        for article_id, url_hash, canonical_url, headline, publisher in articles:
            cur.execute(
                """INSERT INTO public.news_issue_evidence
                   (issue_id, url_hash, canonical_url, source_headline, source_publisher)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (issue_id, url_hash) DO UPDATE SET
                   canonical_url=EXCLUDED.canonical_url,
                   source_headline=EXCLUDED.source_headline,
                   source_publisher=EXCLUDED.source_publisher""",
                (issue_id, url_hash, canonical_url, headline, publisher),
            )
    return len(articles)
