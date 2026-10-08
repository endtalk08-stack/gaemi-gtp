"""Build the shared stock-news result consumed by chat and right-panel views."""

import time

from backend.analysis.news import (
    build_connected_keyword_test,
    build_simple_today_news,
    score_stock_news,
    select_keyword_storyboard_news,
)

from .issue_briefs import build_issue_briefs, build_news_test_articles
from .news_feed import fetch_stock_news


def _empty_news_result():
    return {
        "paired_news_items": [],
        "storyboard_news_items": [],
        "issue_briefs": [],
        "news_test_articles": [],
        "keyword_storyboard": [],
    }


def build_stock_news_result(
    stock_name,
    *,
    market,
    limit=50,
    include_market_stories=False,
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
            include_market_stories=include_market_stories,
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
        article_keyword_result = build_connected_keyword_test(scored_news, stock_name, max_keywords=1)
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
        issue_briefs = build_issue_briefs(
            storyboard_news_items,
            stock_name,
            limit=storyboard_limit,
        )
        news_test_articles = build_news_test_articles(
            storyboard_news_items,
            stock_name,
            limit=storyboard_limit,
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
            "news_test_articles": news_test_articles,
            "keyword_storyboard": keyword_storyboard,
        }
    except Exception as exc:
        print(f"[뉴스] fail: {type(exc).__name__}: {exc}")
        return _empty_news_result()
