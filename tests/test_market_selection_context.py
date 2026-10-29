"""Only US trading-value selection remains; KR news/DART needs no quote."""
import unittest
from unittest.mock import patch

from backend.services import market_rankings as rankings


class MarketSelectionContextTests(unittest.TestCase):
    def setUp(self):
        rankings._MARKET_RESULTS.clear()

    def test_us_value_identity_uses_cached_verified_row(self):
        rankings._remember_market_result("us", "value", [{
            "symbol": "NVDA.O", "name": "NVIDIA",
            "analysis_symbol": "NVDA", "rank": 1,
            "price": 225.78, "change_pct": 1.5,
        }])
        selected = rankings.get_market_selection("us", "value", "NVDA.O", "NVIDIA")
        self.assertEqual(rankings.analysis_ticker_for_selection(selected), "NVDA")
        self.assertEqual(selected["currency"], "USD")
        self.assertEqual(rankings.get_market_menu_rows("us", "value")[0]["rank"], 1)
        self.assertIsNone(rankings.get_market_selection("us", "value", "NVDA.O", "Tesla"))

    def test_removed_menu_names_cannot_resurrect_old_results(self):
        rankings._remember_market_result("kr", "value", [
            {"name": "삼성전자", "symbol": "005930"},
        ])
        rankings._remember_market_result("us", "popular", [
            {"name": "NVIDIA", "symbol": "NVDA.O"},
        ])
        self.assertIsNone(rankings.get_market_selection("kr", "value", "005930"))
        self.assertIsNone(rankings.get_market_selection("us", "popular", "NVDA.O"))
        self.assertEqual(rankings.get_market_menu_rows("us", "popular"), [])
        self.assertEqual(rankings.get_market_menu_rows("kr", "value"), [])

    def test_domestic_news_disclosure_reads_do_not_fetch_price(self):
        from backend.services import engine
        with patch.object(engine, "fetch_stock_price_result",
                          side_effect=AssertionError("unused domestic quote")) as quote, \
             patch.object(engine, "get_shared_stock_news_result",
                          return_value={"issue_briefs": [], "paired_news_items": []}) as news, \
             patch("backend.services.disclosure_transfer.read_snapshot", return_value=[]) as filings:
            result = engine.analyze_stock("삼성전자")
        quote.assert_not_called()
        news.assert_called_once()
        filings.assert_called_once_with("KR", "005930")
        self.assertNotEqual(result.get("ok"), False)
        self.assertEqual(result["price_snapshot"]["current"], 0)
        self.assertEqual(result["disclosures"], [])
        self.assertNotIn("levels", [item["id"] for item in result["sections"]])
        self.assertNotIn("calendar", [item["id"] for item in result["sections"]])


if __name__ == "__main__":
    unittest.main()
