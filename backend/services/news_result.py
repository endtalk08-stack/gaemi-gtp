"""Build the shared stock-news result consumed by chat and right-panel views."""

import hashlib
import json
import time
import urllib.parse
import uuid

from backend.analysis.news import (
    build_connected_keyword_test,
    build_simple_today_news,
    score_stock_news,
    select_keyword_storyboard_news,
)

from .issue_briefs import build_issue_briefs
from .news_detail import extract_structured_article_facts, read_selected_article_details
from .news_feed import fetch_stock_news


def _empty_news_result():
    return {
        "paired_news_items": [],
        "storyboard_news_items": [],
        "issue_briefs": [],
        "keyword_storyboard": [],
    }


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
        trace_id = uuid.uuid4().hex[:10]
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
        storyboard_news_items = select_keyword_storyboard_news(
            paired_news_items,
            limit=storyboard_limit,
        )

        initial_keywords = []
        for rank, item in enumerate(storyboard_news_items, 1):
            url = str(item.get("url") or item.get("link") or "")
            article_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
            parsed = urllib.parse.urlsplit(url)
            public_url = urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, "", "")
            )
            initial_keywords.append(list(item.get("article_keywords") or []))
            print("[news issue audit] " + json.dumps({
                "trace": trace_id, "stock": stock_name, "rank": rank,
                "stage": "selected_before_body", "article": article_id,
                "url": public_url, "title": str(item.get("title") or "")[:140],
                "relation": item.get("relation_type"),
                "owner": item.get("event_owner"),
                "primary_keyword": item.get("storyboard_keyword"),
                "initial_keywords": initial_keywords[-1][:8],
                "keyword_origins": [
                    {
                        "tag": detail.get("label"), "source": detail.get("source"),
                        "owner": detail.get("event_owner")
                    }
                    for detail in (item.get("article_keyword_details") or [])[:8]
                    if isinstance(detail, dict)
                ],
            }, ensure_ascii=False), flush=True)

        # Second pass: read only the already-selected central candidates.  The
        # raw article body never leaves this function; only grounded facts are
        # merged back into the shared result.
        detail_started = time.monotonic()
        detail_texts = read_selected_article_details(
            storyboard_news_items,
            limit=storyboard_limit,
        )
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

        for rank, (item, detail_text) in enumerate(
            zip(storyboard_news_items, detail_texts), 1
        ):
            print("[news issue audit] " + json.dumps({
                "trace": trace_id, "stock": stock_name, "rank": rank,
                "stage": "after_body", "detail_chars": len(detail_text),
                "detail_nonempty": bool(detail_text),
                "before_tags": initial_keywords[rank - 1],
                "after_tags": list(item.get("article_keywords") or [])[:10],
                "detail_read": bool(item.get("detail_read")),
                "detail_facts": sorted(
                    key for key, value in (item.get("detail_facts") or {}).items()
                    if value
                ),
            }, ensure_ascii=False), flush=True)

        # The body is used only while composing the already-selected issue
        # summaries; never attach it to the returned news/UI result.
        brief_inputs = [
            {**item, "_brief_detail_text": detail_texts[index]}
            for index, item in enumerate(storyboard_news_items)
        ]
        issue_diagnostics = []
        issue_briefs = build_issue_briefs(
            brief_inputs,
            stock_name,
            limit=storyboard_limit,
            diagnostics=issue_diagnostics,
        )
        for item in issue_diagnostics:
            print("[news issue audit] " + json.dumps({
                "trace": trace_id, "stock": stock_name,
                "stage": "brief_result", **item,
            }, ensure_ascii=False), flush=True)
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
