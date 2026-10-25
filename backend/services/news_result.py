"""Build the shared stock-news result consumed by chat and right-panel views."""

import copy
import json
import os
import re
import threading
import time

from backend.analysis.news.catalog import STOCK_UNIVERSE, canonical_us_news_name
from backend.analysis.news.stock_identity import news_snapshot_names
from backend.analysis.news import (
    build_connected_keyword_test,
    build_simple_today_news,
    score_stock_news,
    select_keyword_storyboard_news,
)

from .news_byline import strip_leading_news_credit
from .news_freshness import clean_us_snapshot
from .news_identity_registry import resolve_us_news_identity
from .issue_briefs import (
    grounded_issue_display_title,
    _article_excerpt, build_issue_briefs, central_material_brief_supported,
    market_material_title_and_tags,
)
from .company_critical_events import company_critical_title_and_tags
from .business_material_events import business_material_title_and_tags
from .flow_material_events import flow_material_title_and_tags
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



def _fallback_owner_matches(item, stock_name):
    """Fallbacks must not override the existing direct/indirect ownership classifier."""
    relation = str(item.get("relation_type") or "").strip().lower()
    if relation in {"indirect", "mention_only"}:
        return False
    owner = str(item.get("event_owner") or "").strip()
    if owner and not _central_stock_mentioned(owner, stock_name):
        return False
    return True


def _mentions_competing_stock(text, stock_name):
    """Be conservative where a company-specific event has multiple possible owners."""
    for market_stocks in STOCK_UNIVERSE.values():
        for named_stock in market_stocks:
            if named_stock != stock_name and _central_stock_mentioned(text, named_stock):
                return True
    return False


def _stock_owned_material(text, stock_name, extractor):
    """Collect only events whose own sentence has one identifiable company."""
    found_heading, found_tags, tones = "", [], set()
    for clause in re.split(r"(?<=[.!?])\s+", str(text or "")):
        if not _central_stock_mentioned(clause, stock_name):
            continue
        if _mentions_competing_stock(clause, stock_name):
            continue
        heading, tags, tone = extractor(clause)
        if not tags:
            continue
        if not found_heading:
            found_heading = heading
        found_tags.extend(tag for tag in tags if tag not in found_tags)
        if tone and tone != "neutral":
            tones.add(tone)
    direction = next(iter(tones)) if len(tones) == 1 else "mixed" if tones else "neutral"
    return found_heading, found_tags, direction


def _market_snippet_belongs_to_stock(description, stock_name, *, title_has_stock, item):
    """Stock-free macro snippets need a direct headline; never use another firm's news."""
    if _central_stock_mentioned(description, stock_name):
        return True
    return (
        title_has_stock
        and str(item.get("relation_type") or "").strip().lower() == "direct"
        and not _mentions_competing_stock(description, stock_name)
    )


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


def _central_obvious_price_report(item):
    """Skip formulaic trading prints before they crowd out event candidates.

    Conservative, central-only prefilter: the verified article check remains
    authoritative for ambiguous or catalyst-driven price reports.
    """
    text = f"{item.get('title') or ''} {item.get('description') or ''}"
    snapshot_hits = sum(bool(re.search(pattern, text, flags=re.IGNORECASE)) for pattern in (
        r"전\s*거래일\s*(?:보다|대비)",
        r"(?:등락률|장중\s*변동폭)",
        r"(?:고가|최고가)[^.!?]{0,75}?(?:저가|최저가)",
        r"(?:원|달러)에\s*거래(?:됐다|되었|되고|중)",
        r"(?:오전|오후)?\s*\d{1,2}시\s*\d{0,2}분?\s*(?:현재|기준)",
    ))
    if snapshot_hits < 2:
        return False
    if re.search(
        r"공급\s*계약|수주\s*계약|계약\s*체결|"
        r"(?:공장|생산\s*시설).{0,24}(?:증설|확장|건설)|"
        r"자사주\s*(?:매입|소각|취득)|"
        r"(?:투자|실적|매출|영업\s*이익).{0,22}(?:발표|계획|확대|증가|감소)|"
        r"외국인.{0,12}(?:순\s*매도|순\s*매수)|"
        r"허가\s*승인|목표\s*주가\s*(?:상향|하향)",
        text,
        flags=re.IGNORECASE,
    ):
        return False
    return True


def build_stock_news_result(
    stock_name,
    *,
    market,
    limit=50,
    storyboard_limit=3,
    display_timezone="Asia/Seoul",
):
    """Return one shared stock-news result for every screen representation."""
    # The DO snapshot remains keyed by the requested listing name, but all
    # US article/entity checks use its verified catalog company identity.
    if market in ("미국", "us"):
        stock_name = canonical_us_news_name(stock_name)
    # Temporary per-article diagnostics; defaults to the reported stock only.
    # Override with a comma-separated GAEMIGTP_NEWS_DIAGNOSTIC_STOCKS value.
    monitored = {
        name.strip() for name in os.environ.get(
            "GAEMIGTP_NEWS_DIAGNOSTIC_STOCKS", "SK하이닉스"
        ).split(",") if name.strip()
    }
    tracing = stock_name in monitored

    def has_cpi(item):
        text = " ".join(str(item.get(field) or "") for field in ("title", "description", "summary"))
        return bool(re.search(r"\bCPI\b|소비자\s*물가(?:지수)?|물가\s*우려", text, re.IGNORECASE))

    def diag(stage, item=None, **details):
        if not tracing:
            return
        try:
            record = {"stock": stock_name, "stage": stage}
            if item is not None:
                record.update({
                    "title": str(item.get("title") or "")[:150],
                    "url": str(item.get("url") or item.get("link") or "").split("?", 1)[0][:220],
                    "relation": str(item.get("relation_type") or ""),
                    "keywords": list(item.get("storyboard_keywords") or [])[:5],
                    "cpi": has_cpi(item),
                })
            record.update(details)
            print("[news decision] " + json.dumps(record, ensure_ascii=False, default=str), flush=True)
        except Exception:
            pass  # Diagnostics must never change the news result.

    try:
        part_started = time.monotonic()
        raw_news_list = fetch_stock_news(
            stock_name,
            market=market,
            limit=limit,
            raise_on_error=True,
        )
        print(
            f"[analyze news trace] stock={stock_name} part=fetch done "
            f"elapsed={time.monotonic() - part_started:.2f}s items={len(raw_news_list)}",
            flush=True,
        )

        if tracing:
            cpi_rows = [item for item in raw_news_list if has_cpi(item)]
            diag("fetched_summary", total=len(raw_news_list), cpi_count=len(cpi_rows))
            for item in cpi_rows[:12]:
                diag("fetched_cpi", item)

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

        if tracing:
            cpi_rows = [item for item in scored_news if has_cpi(item)]
            diag("scored_summary", total=len(scored_news), cpi_count=len(cpi_rows))
            for item in cpi_rows[:12]:
                diag("scored_cpi", item)

        paired_news_items = build_simple_today_news(
            scored_news,
            stock_name,
            limit=None,
            display_timezone=display_timezone,
        )
        # The shared full-news feed retains its 24-hour window. Only central
        # selection considers older material events from already-fetched news.
        recent_news = build_simple_today_news(
            scored_news,
            stock_name,
            limit=None,
            display_timezone=display_timezone,
            max_age_hours=7 * 24,
        )
        today_keys = {
            row.get("url") or row.get("link") or row.get("title")
            for row in paired_news_items
        }
        older_news = [
            row for row in recent_news
            if (row.get("url") or row.get("link") or row.get("title")) not in today_keys
        ]

        if tracing:
            cpi_today = [item for item in paired_news_items if has_cpi(item)]
            diag("today_summary", total=len(paired_news_items), cpi_count=len(cpi_today))
            for item in paired_news_items:
                if item.get("relation_type") == "direct" or has_cpi(item):
                    diag("today_relevant", item)



        # Priority 1: keep the existing verified issue results; only if there
        # are none, allow an independently evidenced company-critical event.
        # Require explicit company reference in the title to avoid attaching
        # market-wide or third-party corporate events to this stock.
        company_critical_candidates = []
        for item in paired_news_items:
            title = str(item.get("title") or "")
            description = str(item.get("description") or "")
            if not _fallback_owner_matches(item, stock_name):
                continue
            if not _central_stock_mentioned(title, stock_name):
                continue
            title_headline, title_tags, title_tone = _stock_owned_material(
                title, stock_name, company_critical_title_and_tags
            )
            snippet_headline, snippet_tags, snippet_tone = _stock_owned_material(
                description, stock_name, company_critical_title_and_tags
            )
            if not title_tags and not snippet_tags:
                continue
            # The existing relevance classifier must link description-only
            # material to this stock directly, not via incidental mentions.
            if not title_tags and str(item.get("relation_type") or "").lower() != "direct":
                continue
            headline = title_headline or snippet_headline
            tags = list(dict.fromkeys([*title_tags, *snippet_tags]))
            company_critical_candidates.append((
                item, headline, tags, title_tone if title_tags else snippet_tone,
                bool(title_tags),
            ))
            diag("company_critical_candidate", item, critical_tags=tags)
        company_critical_candidates.sort(
            key=lambda entry: (entry[4], str(entry[0].get("published_at") or "")),
            reverse=True,
        )

        # Stage 2: separate real business/industry material from corporate and
        # market policy issues. Headlines carry at most one event while tags
        # retain each independently matched article fact.
        business_material_candidates = []
        for item in paired_news_items:
            title = str(item.get("title") or "")
            description = str(item.get("description") or "")
            if not _fallback_owner_matches(item, stock_name):
                continue
            if not _central_stock_mentioned(title, stock_name):
                continue
            title_h, title_tags, title_dir = _stock_owned_material(
                title, stock_name, business_material_title_and_tags
            )
            desc_h, desc_tags, desc_dir = _stock_owned_material(
                description, stock_name, business_material_title_and_tags
            )
            if not title_tags and not desc_tags:
                continue
            if not title_tags and str(item.get("relation_type") or "").lower() != "direct":
                continue
            business_material_candidates.append((
                item, title_h or desc_h,
                list(dict.fromkeys([*title_tags, *desc_tags])),
                title_dir if title_tags else desc_dir,
                bool(title_tags),
            ))
            diag("business_material_candidate", item, business_tags=title_tags or desc_tags)
        business_material_candidates.sort(
            key=lambda row: (row[4], str(row[0].get("published_at") or "")),
            reverse=True,
        )

        # Stage 4: supplement missing, explicitly reported flow material.
        flow_material_candidates = []
        for item in paired_news_items:
            title = str(item.get("title") or "")
            description = str(item.get("description") or "")
            if not _fallback_owner_matches(item, stock_name):
                continue
            if not _central_stock_mentioned(title, stock_name):
                continue
            title_h, title_tags, title_dir = _stock_owned_material(
                title, stock_name, flow_material_title_and_tags
            )
            desc_h, desc_tags, desc_dir = _stock_owned_material(
                description, stock_name, flow_material_title_and_tags
            )
            if not title_tags and not desc_tags:
                continue
            if not title_tags and str(item.get("relation_type") or "").lower() != "direct":
                continue
            flow_material_candidates.append((
                item, title_h or desc_h,
                list(dict.fromkeys([*title_tags, *desc_tags])),
                title_dir if title_tags else desc_dir, bool(title_tags),
            ))
            diag("flow_material_candidate", item, flow_tags=title_tags or desc_tags)
        flow_material_candidates.sort(
            key=lambda row: (row[4], str(row[0].get("published_at") or "")),
            reverse=True,
        )

        # Same stock-specific news feed, no separate collector.
        # Recognize market material without guessing the cause of a price move.
        market_material_candidates = []
        for item in paired_news_items:
            title = str(item.get("title") or "")
            description = str(item.get("description") or "")
            if not _fallback_owner_matches(item, stock_name):
                continue
            title_has_stock = _central_stock_mentioned(title, stock_name)
            description_has_stock = _central_stock_mentioned(description, stock_name)
            relation = str(item.get("relation_type") or "").strip().lower()
            if not title_has_stock and not (description_has_stock and relation == "direct"):
                continue
            # Match market facts independently: a shared CPI article may name
            # multiple stocks, unlike a one-company credit or contract event.
            title_heading, title_tags = market_material_title_and_tags(title)
            description_heading, description_tags = "", []
            # An incidental mention elsewhere in a long snippet must not
            # validate an event belonging to another named company.
            for clause in re.split(r"(?<=[.!?])\s+", description):
                if not _market_snippet_belongs_to_stock(
                    clause, stock_name, title_has_stock=title_has_stock, item=item
                ):
                    continue
                clause_heading, clause_tags = market_material_title_and_tags(clause)
                if clause_tags and not description_heading:
                    description_heading = clause_heading
                description_tags.extend(
                    tag for tag in clause_tags if tag not in description_tags
                )
            if not title_tags and not description_tags:
                continue
            headline = title_heading or description_heading
            tags = list(dict.fromkeys([*title_tags, *description_tags]))
            market_material_candidates.append((
                item, headline, tags, bool(title_tags), title_has_stock,
            ))
            diag("market_material_candidate", item, material_tags=tags,
                 headline_from="title" if title_tags else "description")
        market_material_candidates.sort(
            key=lambda entry: (
                entry[4],  # Explicitly named stock in headline first
                entry[3],  # Headline evidence above snippet-only evidence
                str(entry[0].get("published_at") or ""),
            ),
            reverse=True,
        )

        def rank_candidates(rows):
            if tracing:
                for row in rows:
                    if _central_obvious_price_report(row) and (
                        row.get("relation_type") == "direct" or has_cpi(row)
                    ):
                        diag("rejected_before_ranking", row, reason="price_snapshot")
            # Give different event keywords a chance before filling remaining
            # verification slots by the existing relevance score.
            pool = select_keyword_storyboard_news(
                [row for row in rows if not _central_obvious_price_report(row)],
                limit=max(1, len(rows)),
                candidate_pool=True,
            )
            limit = max(12, storyboard_limit * 3)
            diverse, remaining, seen_keywords = [], [], set()
            for item in pool:
                keyword = str(item.get("storyboard_keyword") or "").strip()
                if keyword and keyword not in seen_keywords:
                    seen_keywords.add(keyword)
                    diverse.append(item)
                else:
                    remaining.append(item)
            return (diverse + remaining)[:limit]

        # Verify today's candidates first, then fill unoccupied event slots
        # from the existing recent news. No new collector or display path.
        candidate_news = rank_candidates(paired_news_items)
        is_us_24h = market in ("미국", "us", "US")
        # US issues expire by original publication date after 24 hours. Do not
        # spend article fetches on week-old fallback, and do not impose the
        # legacy three-event *display* quota on verified US events.
        if not is_us_24h:
            candidate_news.extend(rank_candidates(older_news))
        issue_count_limit = max(1, len(candidate_news)) if is_us_24h else storyboard_limit
        if tracing:
            queued_keys = {
                (str(item.get("url") or item.get("link") or ""), str(item.get("title") or ""))
                for item in candidate_news
            }
            diag("queue_summary", total=len(candidate_news))
            for item in paired_news_items:
                if item.get("relation_type") != "direct" and not has_cpi(item):
                    continue
                key = (str(item.get("url") or item.get("link") or ""), str(item.get("title") or ""))
                if key in queued_keys:
                    diag("queued_for_body", item)
                else:
                    reason = (
                        "price_snapshot" if _central_obvious_price_report(item)
                        else "no_storyboard_keywords" if not item.get("storyboard_keywords")
                        else "ranking_or_dedup_limit"
                    )
                    diag("rejected_before_body", item, reason=reason)

        detail_started = time.monotonic()
        accepted_articles = []
        storyboard_news_items = []
        verified_body_count = 0
        for start in range(0, len(candidate_news), 3):
            batch = candidate_news[start:start + 3]
            details = read_selected_article_details(
                batch, limit=3, with_sources=True,
            )
            for article, detail in zip(batch, details):
                if detail.get("source") not in {
                    "jsonld_article_body", "article_or_main_paragraphs"
                }:
                    diag("rejected_after_body", article, reason="unverified_article_source",
                         source=detail.get("source"), body_chars=len(detail.get("text") or ""))
                    continue
                verified_body_count += 1
                excerpt = _article_excerpt(detail.get("text") or "")
                if not excerpt:
                    diag("rejected_after_body", article, reason="empty_excerpt",
                         source=detail.get("source"))
                    continue
                if not _central_direct_article(article, excerpt, stock_name):
                    diag("rejected_after_body", article, reason="stock_not_direct_in_opening",
                         body_cpi=has_cpi({"description": excerpt}))
                    continue
                # Only a grounded business/market event belongs in the central
                # notable-news strip. Quote-only reports stay in the shared feed.
                if not central_material_brief_supported(excerpt):
                    diag("rejected_after_body", article, reason="no_supported_material_topic",
                         body_cpi=has_cpi({"description": excerpt}))
                    continue
                diag("accepted_after_body", article, body_cpi=has_cpi({"description": excerpt}))
                candidate = dict(article)
                # Only the central, body-verified copy becomes a direct candidate.
                candidate["relation_type"] = "direct"
                candidate["event_owner"] = stock_name
                candidate["_central_checked_body"] = excerpt
                candidate["_central_checked_full_text"] = detail.get("text") or ""
                candidate["_central_checked_source"] = detail.get("source")
                accepted_articles.append(candidate)
            storyboard_news_items = select_keyword_storyboard_news(
                accepted_articles, limit=issue_count_limit,
            )
            if len(storyboard_news_items) >= issue_count_limit:
                break

        if tracing:
            diag("selection_summary", verified_bodies=verified_body_count,
                 body_accepted=len(accepted_articles), selected=len(storyboard_news_items))
            chosen = {
                (str(item.get("url") or item.get("link") or ""), str(item.get("title") or ""))
                for item in storyboard_news_items
            }
            for item in accepted_articles:
                key = (str(item.get("url") or item.get("link") or ""), str(item.get("title") or ""))
                if key not in chosen:
                    diag("rejected_at_selection", item, reason="selection_keyword_or_duplicate")
            for item in storyboard_news_items:
                diag("selected_issue_article", item)

        if candidate_news and verified_body_count == 0 and not market_material_candidates and not company_critical_candidates and not business_material_candidates and not flow_material_candidates:
            raise RuntimeError('all_candidate_article_bodies_unavailable')

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
            limit=issue_count_limit,
            body_texts=verified_body_texts,
        )

        # Original verified company items always win; the new classification
        # is a strictly secondary fallback for source-grounded severe events.
        if not issue_briefs and company_critical_candidates:
            source, headline, tags, direction, _ = company_critical_candidates[0]
            issue_briefs = [{
                "time": str(source.get("storyboard_time") or "").strip(),
                "reaction_at": str(source.get("published_at") or "").strip(),
                "headline": headline,
                "summary": str(source.get("description") or source.get("title") or "").strip()[:350],
                "tags": tags,
                "stock_names": [stock_name],
                "material_direction": direction,
                "evidence_source": "news_title_description",
            }]
            diag("company_critical_fallback_selected", source, critical_tags=tags)

        # Only if original verified and critical issues are empty.
        if not issue_briefs and business_material_candidates:
            source, headline, tags, direction, _ = business_material_candidates[0]
            issue_briefs = [{
                "time": str(source.get("storyboard_time") or "").strip(),
                "reaction_at": str(source.get("published_at") or "").strip(),
                "headline": headline,
                "summary": str(source.get("description") or source.get("title") or "").strip()[:350],
                "tags": tags,
                "stock_names": [stock_name],
                "material_direction": direction,
                "evidence_source": "news_title_description",
            }]
            diag("business_material_fallback_selected", source, business_tags=tags)

        # Then keep the existing market material fallback unchanged.
        if not issue_briefs and market_material_candidates:
            source, headline, tags, _, _ = market_material_candidates[0]
            issue_briefs = [{
                "time": str(source.get("storyboard_time") or "").strip(),
                "reaction_at": str(source.get("published_at") or "").strip(),
                "headline": headline,
                "summary": str(source.get("description") or source.get("title") or "").strip()[:350],
                "tags": tags,
                "stock_names": [stock_name],
                "evidence_source": "news_title_description",
            }]
            diag("market_material_fallback_selected", source, material_tags=tags)

        # Last fallback: explicit stock-level supply/demand disclosures.
        if not issue_briefs and flow_material_candidates:
            source, headline, tags, direction, _ = flow_material_candidates[0]
            issue_briefs = [{
                "time": str(source.get("storyboard_time") or "").strip(),
                "reaction_at": str(source.get("published_at") or "").strip(),
                "headline": headline,
                "summary": str(source.get("description") or source.get("title") or "").strip()[:350],
                "tags": tags,
                "stock_names": [stock_name],
                "material_direction": direction,
                "evidence_source": "news_title_description",
            }]
            diag("flow_material_fallback_selected", source, flow_tags=tags)

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
            # Presentation-only: include the already-fetched, dated company news
            # from the existing 7-day provider window. AI/issue evidence keeps
            # using the untouched 24-hour paired_news_items. Snapshot TTL is 24h.
            "panel_news_items": recent_news[:20],
            "storyboard_news_items": storyboard_news_items,
            "issue_briefs": issue_briefs,
            "keyword_storyboard": keyword_storyboard,
            "_news_status": "ok",
        }
    except Exception as exc:
        print(f"[뉴스] fail: {type(exc).__name__}: {exc}")
        return {**_empty_news_result(), "_news_status": "error"}


# Render reads DigitalOcean-processed news; it does not start its own news processing.

def _sanitize_news_display_briefs(result, *, market=None):
    """Remove only byline boilerplate from visible summaries, not the source data."""
    if not isinstance(result, dict):
        return result
    for brief in result.get("issue_briefs") or []:
        if isinstance(brief, dict) and isinstance(brief.get("summary"), str):
            brief["summary"] = strip_leading_news_credit(brief["summary"])
            brief["headline"] = grounded_issue_display_title(brief)
            # Earlier AI worker versions added unrequested publication/AI labels.
            # Show only the existing concise HH:MM; leave persisted evidence untouched.
            timestamp = brief.get("time")
            if isinstance(timestamp, str):
                publication = re.fullmatch(
                    r"기사 발행 \d{2}\.\d{2} (\d{2}:\d{2})(?: · AI 분석 \d{2}:\d{2})?",
                    timestamp.strip(),
                )
                ai_time = re.fullmatch(
                    r"AI 분석 (?:\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2})",
                    timestamp.strip(),
                )
                if publication or ai_time:
                    brief["time"] = (publication or ai_time).group(1)
    return result


def _read_worker_news_snapshot(stock_name, *, market, limit, storyboard_limit, display_timezone):
    """Read the DigitalOcean worker's valid 24h output before doing web/API work."""
    database_url = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not database_url:
        return None
    try:
        import psycopg
        with psycopg.connect(database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT result_payload
                    FROM public.news_processed_snapshots
                    WHERE market=%s AND stock_name=%s
                      AND result_limit=%s AND storyboard_limit=%s
                      AND display_timezone=%s AND expires_at>now()
                    LIMIT 1
                    """,
                    (market, str(stock_name), int(limit), int(storyboard_limit),
                     display_timezone),
                )
                row = cur.fetchone()
        result = row[0] if row else None
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict) or result.get("_news_status") == "error":
            return None
        if not isinstance(result.get("issue_briefs"), list):
            return None
        return result
    except Exception as exc:
        print("[processed news] worker snapshot unavailable: "
              + type(exc).__name__, flush=True)
        return None


def get_shared_stock_news_result(stock_name, *, market, limit=50, storyboard_limit=3,
                                 display_timezone="Asia/Seoul", symbol=None, issue_mode="auto"):
    """Read the existing DigitalOcean snapshot only; never collect or save news."""
    names = (resolve_us_news_identity(stock_name, symbol=symbol)["snapshot_names"]
             if market in ("미국", "us") else [str(stock_name)])
    worker_result = None
    for candidate_name in names:
        worker_result = _read_worker_news_snapshot(
            candidate_name, market=market, limit=limit,
            storyboard_limit=storyboard_limit,
            display_timezone=display_timezone,
        )
        if worker_result is not None:
            break
    if worker_result is None:
        return {**_empty_news_result(), "_news_status": "unavailable"}
    worker_result = copy.deepcopy(worker_result)
    if market in ("미국", "us"):
        worker_result = clean_us_snapshot(worker_result, issue_mode=issue_mode)
    return _sanitize_news_display_briefs(worker_result, market=market)
