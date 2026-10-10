import unittest
from unittest.mock import patch

from backend.services.news_feed import _select_stock_news_with_source_reserve, fetch_stock_news


class StockNewsQueryTests(unittest.TestCase):
    @patch("backend.services.news_feed.sec_filings.fetch_recent_filings", return_value=[])
    @patch("backend.services.news_feed.official_company_news.fetch_company_news", return_value=[])
    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_us_stock_uses_all_company_aliases(self, fetch_queries, official_news, sec_news):
        fetch_stock_news(
            "알파벳",
            market="미국",
            limit=20,
            include_market_stories=False,
        )

        queries = fetch_queries.call_args.args[0]
        self.assertEqual(
            queries,
            ["알파벳", "GOOGL", "GOOG", "구글", "google", "alphabet"],
        )

    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_domestic_stock_keeps_existing_alias_cap(self, fetch_queries):
        fetch_stock_news(
            "SK하이닉스",
            market="국내",
            limit=20,
            include_market_stories=False,
        )

        queries = fetch_queries.call_args.args[0]
        self.assertEqual(
            queries,
            ["SK하이닉스", "sk하이닉스", "하이닉스", "sk hynix"],
        )


    def test_trusted_official_news_survives_final_limit(self):
        general = [
            {
                "title": f"general-{index}",
                "url": f"https://example.com/general-{index}",
                "source_type": "naver",
            }
            for index in range(60)
        ]
        official = [
            {
                "title": "NVIDIA official update",
                "url": "https://blogs.nvidia.com/official-update",
                "source_type": "official_company",
            }
        ]

        selected = _select_stock_news_with_source_reserve(
            [*general, *official],
            limit=50,
        )

        self.assertEqual(len(selected), 50)
        self.assertTrue(
            any(item["source_type"] == "official_company" for item in selected)
        )

    def test_sec_rows_are_reserved_without_stock_specific_rules(self):
        general = [
            {
                "title": f"general-{index}",
                "url": f"https://example.com/general-{index}",
                "source_type": "naver",
            }
            for index in range(20)
        ]
        sec = [
            {
                "title": "8-K filing",
                "url": "https://sec.example/8-k",
                "source_type": "sec_filing",
            }
        ]

        selected = _select_stock_news_with_source_reserve(
            [*general, *sec],
            limit=10,
        )

        self.assertEqual(len(selected), 10)
        self.assertTrue(any(item["source_type"] == "sec_filing" for item in selected))


if __name__ == "__main__":
    unittest.main()
