import unittest
from unittest.mock import patch

import backend.services.r2_news_uploader  # Ensure patch target is imported.
from backend.services.naver_news_r2 import (
    build_naver_snapshot,
    publish_naver_news,
)
from backend.services.news_feed import fetch_naver_news


class NaverNewsR2Tests(unittest.TestCase):
    def test_normalises_naver_records_without_fabricating_article_body(self):
        snapshot = build_naver_snapshot([
            {
                "title": "<b>AI 반도체</b> 공급 계약",
                "description": "회사 발표 요약",
                "source": "전자신문",
                "published_at": "2026-11-26T01:00:00+00:00",
                "url": "https://example.com/news/1",
            },
        ], generated_at="2026-11-26T02:00:00+00:00")

        self.assertTrue(snapshot["ok"])
        self.assertEqual(snapshot["count"], 1)
        self.assertEqual(snapshot["items"][0]["title"], "<b>AI 반도체</b> 공급 계약")
        self.assertEqual(snapshot["items"][0]["summary"], "회사 발표 요약")
        self.assertNotIn("body", snapshot["items"][0])

    def test_merges_existing_sources_and_deduplicates_by_url(self):
        old = {
            "ok": True,
            "items": [
                {"title": "기존 SEC 기사", "url": "https://sec.example/1",
                 "published_at": "2026-11-25T00:00:00+00:00"},
                {"title": "오래된 중복 제목", "url": "https://example.com/news/1"},
            ],
        }
        snapshot = build_naver_snapshot([
            {"title": "새 네이버 기사", "url": "https://example.com/news/1",
             "description": "새 설명", "published_at": "2026-11-26T01:00:00+00:00"},
        ], existing_snapshot=old)

        self.assertEqual(snapshot["count"], 2)
        self.assertEqual(snapshot["items"][0]["title"], "새 네이버 기사")
        self.assertEqual(snapshot["items"][1]["title"], "기존 SEC 기사")

    @patch("backend.services.news_feed._fetch_queries")
    def test_naver_market_feed_is_tagged_for_pages_market_section(self, fetch_queries):
        fetch_queries.return_value = [{
            "title": "미국 증시 주요 뉴스",
            "description": "시장 요약",
            "url": "https://example.com/market",
            "published_at": "2026-11-26T01:00:00+00:00",
            "source": "Example",
        }]
        items = fetch_naver_news(["미국 증시"], section="market")
        self.assertEqual(items[0]["news_section"], "market")
        self.assertEqual(items[0]["news_sections"], ["market"])
        self.assertEqual(items[0]["category"], "시장동향")

    @patch("backend.services.news_feed._fetch_queries")
    def test_naver_stock_feed_is_tagged_for_pages_stock_section(self, fetch_queries):
        fetch_queries.return_value = [{
            "title": "삼성전자 실적 발표",
            "description": "실적 내용",
            "url": "https://example.com/stock",
            "published_at": "2026-11-26T01:00:00+00:00",
            "source": "Example",
        }]
        items = fetch_naver_news(["삼성전자"], section="stock")
        self.assertEqual(items[0]["news_section"], "stock")
        self.assertEqual(items[0]["news_sections"], ["stock"])
        self.assertEqual(items[0]["category"], "종목")

    def test_empty_or_invalid_input_does_not_build_an_empty_snapshot(self):
        with self.assertRaisesRegex(ValueError, "no_publishable_naver_news"):
            build_naver_snapshot([{"title": "제목만 있고 링크 없음"}])

    @patch("backend.services.r2_news_uploader.upload_file", return_value=True)
    @patch("backend.services.r2_news_uploader.read_latest_news_snapshot", return_value=None)
    def test_publishes_to_existing_latest_object_key(self, read_snapshot, upload):
        snapshot = publish_naver_news([
            {"title": "네이버 기사", "url": "https://example.com/1"},
        ])
        self.assertTrue(snapshot["ok"])
        self.assertEqual(upload.call_args.kwargs["object_key"], "news/latest.json")


if __name__ == "__main__":
    unittest.main()
