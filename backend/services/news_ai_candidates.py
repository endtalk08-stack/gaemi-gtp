"""Choose a bounded, diverse set of already verified articles for optional AI.

No new scraping, relaxed source verification, or change to news/central display.
Distinct material types are represented before a repeated topic consumes all
ten inputs; a second pass may retain separate events from the same topic.
"""
import re

from backend.database.news_url import news_url_hash

_VERIFIED = {"jsonld_article_body", "article_or_main_paragraphs"}


def _topic(article):
    """A *soft* grouping signal, not a determination that events are equal."""
    labels = ([article.get("storyboard_keyword")] +
              list(article.get("storyboard_keywords") or []) +
              list(article.get("grounded_tags") or []))
    for label in labels:
        compact = re.sub(r"\s+", "", str(label or "")).casefold()
        if compact:
            return compact
    # Unlabelled articles are distinct candidates; do not group all into one.
    return "unlabelled:" + (news_url_hash(article.get("url") or article.get("link")) or
                           re.sub(r"\s+", "", str(article.get("title") or "")))


def select_verified_ai_candidates(articles, limit=10):
    """Return at most 10 *independently body-verified* article inputs.

    Preserve candidate order within each topic. Avoid duplicate canonical
    URLs, but never mistake a shared topic for proof of a duplicate event.
    """
    max_items = max(0, min(int(limit), 10))
    if max_items == 0:
        return []
    unique, seen_urls = [], set()
    for row in articles:
        if row.get("_central_checked_source") not in _VERIFIED:
            continue
        body = str(row.get("_central_checked_full_text") or "").strip()
        if len(body) < 60:
            continue
        url = str(row.get("url") or row.get("link") or "").strip()
        digest = news_url_hash(url)
        if not digest or digest in seen_urls:
            continue
        seen_urls.add(digest)
        unique.append((row, body, url, _topic(row)))

    first_pass, repeats, covered = [], [], set()
    for row in unique:
        topic = row[3]
        if topic not in covered:
            first_pass.append(row)
            covered.add(topic)
        else:
            repeats.append(row)
    chosen = (first_pass + repeats)[:max_items]
    return [{
        "title": str(row.get("title") or ""),
        "body": body,
        "url": url,
        "time": str(row.get("storyboard_time") or ""),
        "reaction_at": str(row.get("published_at") or ""),
    } for row, body, url, _ in chosen]
