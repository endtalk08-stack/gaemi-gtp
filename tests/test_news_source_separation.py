"""Regression tests for news-provider separation and the R2-first worker mode."""

import os
from unittest.mock import patch

from backend.services import news_feed, news_worker


def test_naver_items_keep_provider_separate_from_publisher():
    item = news_feed._build_item(
        {
            "title": "테스트 뉴스",
            "description": "기사 요약",
            "link": "https://news.example/article",
            "originallink": "https://news.example/article",
            "pubDate": "Thu, 26 Nov 2026 07:00:00 GMT",
        },
        query="테스트",
        category="시장동향",
    )

    assert item["provider"] == "naver"
    assert item["source_provider"] == "naver"
    assert item["source"] == "news.example"


def test_tradingview_collection_is_paused():
    assert news_feed.TRADINGVIEW_NEWS_ENABLED is False


def test_news_worker_defaults_to_r2():
    with patch.dict(os.environ, {}, clear=True):
        assert news_worker.news_storage_mode() == "r2"
