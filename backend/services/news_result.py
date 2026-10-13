"""Build the shared stock-news result consumed by chat and right-panel views."""

import re
import time

from backend.analysis.news.catalog import STOCK_UNIVERSE
from backend.analysis.news import (
    build_connected_keyword_test,
    build_simple_today_news,
    score_stock_news,
    select_keyword_storyboard_news,
)

from .issue_briefs import _article_excerpt, build_issue_briefs
from .news_detail import extract_structured_article_facts, read_selected_article_details
from .news_feed import fetch_stock_news


def _empty_news_result():
    return {
        "paired_news_items": [],
        "storyboard_news_items": [],
        "issue_briefs": [],
        "keyword_storyboard": [],
    }


def _central_stock_mentioned(text, stock_name):
    """Match the selected company, avoiding short-name partial-word collisions."""
    names = [str(stock_name or "").strip()]
    for stocks in STOCK_UNIVERSE.values():
        if stock_name in stocks:
            names.extend(stocks[stock_name])
            break
    if stock_name == "삼성전자":
        names.append("삼전")

    text = str(text or "").lower()
    for name in names:
        alias = str(name or "").strip().lower()
        if not alias:
            continue
        if alias == "삼전":
            pattern = r"(?<![가-힣a-z0-9])삼전(?=$|[^가-힣a-z0-9]|[은는이가의을를도와과])"
        elif re.fullmatch(r"[a-z0-9.]+", alias):
            pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        elif len(alias) <= 2:
            pattern = rf"(?<![가-힣a-z0-9]){re.escape(alias)}(?=$|[^가-힣a-z0-9]|[은는이가의을를도])"
        else:
            pattern = re.escape(alias)
        if re.search(pattern, text):
            return True
    return False


def _central_direct_article(article, original_excerpt, stock_name):
    """Use a verified article's opening sentences, not keyword matches alone."""
    title = str(article.get("title") or "")
    excerpt = str(original_excerpt or "")
    title_has_stock = _central_stock_mentioned(title, stock_name)
    body_has_stock = _central_stock_mentioned(excerpt, stock_name)

    if title_has_stock and body_has_stock:
        return True
    if title_has_stock:
        # News often names the company in the title and uses 'the company'
        # in its first or second sentence. Do not require the name again.
        return bool(re.search(
            r"(?:^|[.!?]\s+|[,，]\s+)(?:이\s*)?"
            r"(?:회사|동사|기업|업체)(?:는|가|의|측은|측이)",
            excerpt,
        ))
    if body_has_stock:
        # A generic headline is acceptable only if the selected company
        # clearly appears as the subject at the beginning of the article.
        opening = re.split(r"(?<=[.!?])\s+", excerpt, maxsplit=1)[0]
        return _central_stock_mentioned(opening[:180], stock_name)
    return False


def build_stock_news_result(
    stock_name,
    *,
    market,
    limit=50,
    storyboard_limit=3,
    display_timezone="Asia/Seoul",
):
    """Return one shared stock-news result for every screen representation."""
    try:
        part_started = time.monotonic()
        raw_news_list = fetch_stock_news(
            stock_name,
            market=market,
            limit=limit,
        )
        print(
            f"[analyze news trace] stock={stock_name} part=fetch done "
            f"elapsed={time.monotonic() - part_started:.2f}s items={len(raw_news_list)}",
            flush=True,
        )

        part_started = time.monotonic()
        scored_news = score_stock_news(raw_news_list, stock_name)
        print(
            f"[analyze news trace] stock={stock_name} part=score done "
            f"elapsed={time.monotonic() - part_started:.2f}s items={len(scored_news)}",
            flush=True,
        )

        part_started = time.monotonic()
        article_keyword_result = build_connected_keyword_test(scored_news, stock_name, max_keywords=3)
        print(
            f"[analyze news trace] stock={stock_name} part=keywords done "
            f"elapsed={time.monotonic() - part_started:.2f}s",
            flush=True,
        )
        for article, keyword_result in zip(scored_news, article_keyword_result.get("articles", [])):
            article["article_keywords"] = keyword_result.get("keywords", [])
            article["article_keyword_details"] = keyword_result.get("keyword_details", [])
            article["grounded_tags"] = keyword_result.get("grounded_tags", [])
            article["stock_entities"] = keyword_result.get("stock_entities", [])
            article["event_owner"] = keyword_result.get("event_owner", "")
            article["relation_type"] = keyword_result.get("relation_type", "unknown")

        paired_news_items = build_simple_today_news(
            scored_news,
            stock_name,
            limit=None,
            display_timezone=display_timezone,
        )
        # Rank more candidates without discarding similar headlines yet.
        # A verified body decides relevance and whether two reports are one event.
        candidate_news = select_keyword_storyboard_news(
            paired_news_items,
            limit=max(9, storyboard_limit * 4),
            candidate_pool=True,
        )

        detail_started = time.monotonic()
        accepted_articles = []
        storyboard_news_items = []
        for start in range(0, len(candidate_news), 3):
            batch = candidate_news[start:start + 3]
            details = read_selected_article_details(
                batch, limit=3, with_sources=True,
            )
            for article, detail in zip(batch, details):
                if detail.get("source") not in {
                    "jsonld_article_body", "article_or_main_paragraphs"
                }:
                    continue
                excerpt = _article_excerpt(detail.get("text") or "")
                if not excerpt or not _central_direct_article(article, excerpt, stock_name):
                    continue
                candidate = dict(article)
                # Only the central, body-verified copy becomes a direct candidate.
                candidate["relation_type"] = "direct"
                candidate["event_owner"] = stock_name
                candidate["_central_checked_body"] = excerpt
                candidate["_central_checked_full_text"] = detail.get("text") or ""
                candidate["_central_checked_source"] = detail.get("source")
                accepted_articles.append(candidate)
            storyboard_news_items = select_keyword_storyboard_news(
                accepted_articles, limit=storyboard_limit,
            )
            if len(storyboard_news_items) >= storyboard_limit:
                break

        # Keep full article bodies local to this function, not in API records.
        detail_records = [
            {
                "text": article.pop("_central_checked_full_text", ""),
                "source": article.pop("_central_checked_source", "fetch_failed"),
            }
            for article in storyboard_news_items
        ]
        for article in storyboard_news_items:
            article.pop("_central_checked_body", None)
        detail_texts = [record.get("text") or "" for record in detail_records]
        if any(detail_texts):
            detail_inputs = []
            for item, detail_text in zip(storyboard_news_items, detail_texts):
                enriched = dict(item)
                if detail_text:
                    enriched["description"] = detail_text
                    enriched["summary"] = detail_text
                detail_inputs.append(enriched)

            detail_keyword_result = build_connected_keyword_test(
                detail_inputs,
                stock_name,
                max_keywords=3,
            )
            for item, detail_text, detail_result in zip(
                storyboard_news_items,
                detail_texts,
                detail_keyword_result.get("articles", []),
            ):
                if not detail_text:
                    continue
                direct_details = [
                    detail for detail in (detail_result.get("keyword_details") or [])
                    if str((detail or {}).get("relation_type") or "") == "direct"
                ]
                direct_labels = [
                    str((detail or {}).get("label") or "").strip()
                    for detail in direct_details
                    if str((detail or {}).get("label") or "").strip()
                ]
                item["article_keywords"] = list(dict.fromkeys(
                    list(item.get("article_keywords") or []) + direct_labels
                ))
                existing_details = list(item.get("article_keyword_details") or [])
                existing_labels = {
                    str((detail or {}).get("label") or "").strip()
                    for detail in existing_details
                }
                item["article_keyword_details"] = existing_details + [
                    detail for detail in direct_details
                    if str((detail or {}).get("label") or "").strip() not in existing_labels
                ]
                item["grounded_tags"] = list(dict.fromkeys(
                    list(item.get("grounded_tags") or [])
                    + list(detail_result.get("grounded_tags") or [])
                ))
                detail_owner = str(detail_result.get("event_owner") or "").strip()
                detail_relation = str(detail_result.get("relation_type") or "").strip()
                facts_item = dict(item)
                if detail_owner and detail_relation == "direct":
                    facts_item["event_owner"] = detail_owner
                    facts_item["relation_type"] = detail_relation
                item["detail_facts"] = extract_structured_article_facts(
                    detail_text,
                    facts_item,
                    stock_name,
                    grounded_tags=item.get("grounded_tags") or [],
                )
                item["detail_read"] = True
        print(
            f"[analyze news trace] stock={stock_name} part=detail done "
            f"elapsed={time.monotonic() - detail_started:.2f}s "
            f"read={sum(1 for value in detail_texts if value)}",
            flush=True,
        )

        # The central brief is shown only for a verified article body, never
        # for a meta description, arbitrary page paragraphs or a failed fetch.
        verified_body_texts = [
            record.get("text") or ""
            if record.get("source") in {"jsonld_article_body", "article_or_main_paragraphs"}
            else ""
            for record in detail_records
        ]
        issue_briefs = build_issue_briefs(
            storyboard_news_items,
            stock_name,
            limit=storyboard_limit,
            body_texts=verified_body_texts,
        )
        # Diagnostic counts only: trace where central issues drop out without
        # changing the shared news, selection, or presentation results.
        central_eligible = [
            item for item in paired_news_items
            if str(item.get("relation_type") or "unknown").strip().lower()
            not in {"indirect", "mention_only"}
        ]
        direct_count = sum(
            1 for item in paired_news_items
            if str(item.get("relation_type") or "").strip().lower() == "direct"
        )
        keyword_pass_count = sum(
            1 for item in central_eligible
            if any(str(value).strip() for value in (item.get("storyboard_keywords") or []))
        )
        print(
            f"[analyze news funnel] stock={stock_name} "
            f"period=rolling_24h "
            f"period_pass={len(paired_news_items)} "
            f"direct={direct_count} eligible={len(central_eligible)} "
            f"keyword_pass={keyword_pass_count} "
            f"selected={len(storyboard_news_items)} briefs={len(issue_briefs)}",
            flush=True,
        )
        keyword_storyboard = [
            {
                "time": item.get("storyboard_time", ""),
                "keywords": item.get("storyboard_keywords", [])[:3],
                "keyword_tones": item.get("storyboard_keyword_tones", {}),
                "grounded_tags": item.get("grounded_tags", [])[:4],
                "stock_entities": item.get("stock_entities", [])[:4],
            }
            for item in storyboard_news_items
            if item.get("storyboard_keyword")
        ]
        return {
            "paired_news_items": paired_news_items,
            "storyboard_news_items": storyboard_news_items,
            "issue_briefs": issue_briefs,
            "keyword_storyboard": keyword_storyboard,
        }
    except Exception as exc:
        print(f"[뉴스] fail: {type(exc).__name__}: {exc}")
        return _empty_news_result()
