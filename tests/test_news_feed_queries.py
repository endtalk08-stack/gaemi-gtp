import unittest
from unittest.mock import patch

from backend.services.news_feed import fetch_stock_news


class StockNewsQueryTests(unittest.TestCase):
    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_us_stock_uses_all_company_aliases(self, fetch_queries):
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


if __name__ == "__main__":
    unittest.main()
