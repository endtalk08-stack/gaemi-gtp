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

    def test_us_top20_chat_reads_existing_verified_rows_only(self):
        from backend.services import ai_test as chat
        rankings._remember_market_result("us", "value", [{
            "symbol": "NVDA", "name": "NVIDIA", "rank": 1,
            "trading_value": 1230000000.0, "change_pct": 1.5,
        }])
        with patch.object(chat, "get_market_menu_rows",
                          wraps=rankings.get_market_menu_rows) as read:
            answer = chat._market_ranking_reply("미국 거래대금 TOP 1 알려줘")
        self.assertIn("1위 NVIDIA", answer)
        self.assertIn("$1,230,000,000", answer)
        read.assert_called_once_with("us", "value")

    def test_us_top20_chat_without_saved_rows_never_recollects(self):
        from backend.services import ai_test as chat
        self.assertEqual(
            chat._market_ranking_reply("미국 거래대금 TOP 20 알려줘"),
            "미국 거래대금 데이터를 지금 확인하지 못했어.",
        )

    def test_removed_rank_menus_are_not_handled_as_existing_results(self):
        from backend.services import ai_test as chat
        for question in (
            "국내 거래대금 TOP 20 알려줘",
            "국내 인기순위 TOP 20 알려줘",
            "미국 인기순위 TOP 20 알려줘",
        ):
            with self.subTest(question=question):
                self.assertIsNone(chat._market_ranking_request(question))
                self.assertIsNone(chat._market_ranking_reply(question))

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
