import unittest
from unittest.mock import patch

from backend.services.news_feed import fetch_stock_news


class StockNewsQueryTests(unittest.TestCase):
    def setUp(self):
        self.official_patcher = patch(
            "backend.services.news_feed.official_company_news.fetch_company_news",
            return_value=[],
        )
        self.sec_patcher = patch(
            "backend.services.news_feed.sec_filings.fetch_recent_filings",
            return_value=[],
        )
        self.official_fetch = self.official_patcher.start()
        self.sec_fetch = self.sec_patcher.start()
        self.addCleanup(self.official_patcher.stop)
        self.addCleanup(self.sec_patcher.stop)

    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_us_stock_uses_all_company_aliases(self, fetch_queries):
        fetch_stock_news(
            "알파벳", market="미국", limit=20,
        )
        fetch_queries.assert_called_once()
        self.assertEqual(
            fetch_queries.call_args.args[0],
            ["알파벳", "GOOGL", "GOOG", "구글", "google", "alphabet"],
        )

    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_us_stock_restores_official_and_sec_sources(self, fetch_queries):
        fetch_stock_news("알파벳", market="미국", limit=20)
        self.official_fetch.assert_called_once()
        self.sec_fetch.assert_called_once()
        self.assertEqual(self.sec_fetch.call_args.args[1], "GOOGL")

    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_domestic_stock_keeps_existing_alias_cap(self, fetch_queries):
        fetch_stock_news(
            "SK하이닉스", market="국내", limit=20,
        )
        fetch_queries.assert_called_once()
        self.assertEqual(
            fetch_queries.call_args.args[0],
            ["SK하이닉스", "sk하이닉스", "하이닉스", "sk hynix"],
        )

    @patch("backend.services.news_feed._fetch_queries")
    def test_english_foreign_press_kept_for_us_stock(self, fetch_queries):
        fetch_queries.return_value = [
            {
                "title": "Alphabet signs a new technology agreement",
                "description": "Alphabet signed an agreement with a partner.",
                "url": "https://www.reuters.com/technology/alpha-agreement",
                "published_at": "",
                "source": "Reuters",
            },
            {
                "title": "CNBC reports on Google cloud investment",
                "description": "Google plans an investment in cloud infrastructure.",
                "url": "https://www.cnbc.com/2026/10/10/google-cloud.html",
                "published_at": "",
                "source": "CNBC",
            },
        ]
        result = fetch_stock_news(
            "알파벳", market="미국", limit=20,
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(
            {item["source"] for item in result}, {"Reuters", "CNBC"},
        )
        fetch_queries.assert_called_once()


if __name__ == "__main__":
    unittest.main()
