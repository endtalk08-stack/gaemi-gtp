"""Build the shared stock-news result consumed by chat and right-panel views."""

import copy
import json
import os
import re
import threading
import time

from backend.analysis.news.catalog import STOCK_UNIVERSE
from backend.analysis.news import (
    build_connected_keyword_test,
    build_simple_today_news,
    score_stock_news,
    select_keyword_storyboard_news,
)

from .issue_briefs import (
    _article_excerpt, build_issue_briefs, central_material_brief_supported,
    market_material_title_and_tags,
)
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


        # Same stock-specific news feed, no separate collector.
        # Recognize market material without guessing the cause of a price move.
        market_material_candidates = []
        for item in paired_news_items:
            title = str(item.get("title") or "")
            description = str(item.get("description") or "")
            title_has_stock = _central_stock_mentioned(title, stock_name)
            description_has_stock = _central_stock_mentioned(description, stock_name)
            relation = str(item.get("relation_type") or "").strip().lower()
            # No broad market headlines assigned to a company by incidental
            # mention. The company must be in the title, or be a direct
            # subject of the snippet according to the existing classifier.
            if not title_has_stock and not (description_has_stock and relation == "direct"):
                continue
            # Check title and snippet independently: never construct a signal
            # from half a phrase in the title and the other half in the snippet.
            title_heading, title_tags = market_material_title_and_tags(title)
            description_heading, description_tags = market_material_title_and_tags(description)
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
        candidate_news.extend(rank_candidates(older_news))
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
                accepted_articles, limit=storyboard_limit,
            )
            if len(storyboard_news_items) >= storyboard_limit:
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

        if candidate_news and verified_body_count == 0 and not market_material_candidates:
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
            limit=storyboard_limit,
            body_texts=verified_body_texts,
        )

        # Only when the original body-verified issues are empty: trust clearly
        # stated market facts in the source title/description, not a price move.
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
            "_news_status": "ok",
        }
    except Exception as exc:
        print(f"[뉴스] fail: {type(exc).__name__}: {exc}")
        return {**_empty_news_result(), "_news_status": "error"}


# Reuse the exact stock-news result across central analysis and market-menu issues.
# No independent sidebar collector or separate issue interpretation.
_SHARED_NEWS_CACHE = {}
_SHARED_NEWS_LOCK = threading.Lock()
_SHARED_NEWS_KEY_LOCKS = {}
_SHARED_NEWS_TTL = 15 * 60


def get_shared_stock_news_result(stock_name, *, market, limit=50, storyboard_limit=3,
                                 display_timezone="Asia/Seoul"):
    key = (str(stock_name), market, int(limit), int(storyboard_limit), display_timezone)
    with _SHARED_NEWS_LOCK:
        lock = _SHARED_NEWS_KEY_LOCKS.setdefault(key, threading.Lock())
    with lock:
        with _SHARED_NEWS_LOCK:
            cached = _SHARED_NEWS_CACHE.get(key)
            if cached and time.monotonic() - cached[0] < _SHARED_NEWS_TTL:
                return copy.deepcopy(cached[1])
        result = build_stock_news_result(
            stock_name, market=market, limit=limit,
            storyboard_limit=storyboard_limit, display_timezone=display_timezone,
        )
        if result.get("_news_status") == "error":
            return result
        with _SHARED_NEWS_LOCK:
            if len(_SHARED_NEWS_CACHE) >= 96:
                _SHARED_NEWS_CACHE.clear()
            _SHARED_NEWS_CACHE[key] = (time.monotonic(), copy.deepcopy(result))
        return result
