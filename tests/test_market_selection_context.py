"""Selected sidebar rows reuse the existing processed market menu results."""
import unittest
from unittest.mock import patch

from backend.services import market_rankings as rankings


class MarketSelectionContextTests(unittest.TestCase):
    def setUp(self):
        rankings._MARKET_RESULTS.clear()

    def test_four_menus_share_verified_stock_selection_without_another_fetch(self):
        kr = {"items": [{"itemCode": "005930", "price": {
            "itemName": "삼성전자", "marketType": "KOSPI",
            "krx": {"currentPrice": "234000", "changeRate": "-6.59",
                    "tradingValue": "5916362000000"}
        }}]}
        us = {"items": [{"itemCode": "NVDA.O", "price": {
            "itemName": "엔비디아", "symbolCode": "NVDA", "currentPrice": "225.78",
            "changeRate": "+2.50", "tradingValue": "3600000000",
            "sectorName": "반도체"
        }}]}
        with (
            patch.object(rankings, "get_stock_industries", return_value={}) as industry,
            patch.object(rankings, "fetch_kr_popular_ranking_raw", return_value=kr) as kr_pop,
            patch.object(rankings, "fetch_kr_trading_value_ranking_raw", return_value=kr) as kr_val,
            patch.object(rankings, "fetch_us_popular_ranking_raw", return_value=us) as us_pop,
            patch.object(rankings, "fetch_us_trading_value_ranking_raw", return_value=us) as us_val,
        ):
            kr_popular = rankings.build_kr_popular_result()
            kr_value = rankings.build_kr_trading_value_result()
            us_popular = rankings.build_us_popular_result()
            us_value = rankings.build_us_trading_value_result()
            for menu in ("popular", "value"):
                selected_kr = rankings.get_market_selection("kr", menu, "005930", stock="삼성전자")
                selected_us = rankings.get_market_selection("us", menu, "NVDA.O", stock="엔비디아")
                self.assertEqual(selected_kr["industry"], None)
                self.assertEqual(selected_kr["trading_value"], 5916362000000.0)
                self.assertEqual(selected_us["industry"], "반도체")
                self.assertEqual(rankings.analysis_ticker_for_selection(selected_kr), "005930.KS")
                self.assertEqual(rankings.analysis_ticker_for_selection(selected_us), "NVDA")
                self.assertEqual(selected_kr["market"], "kr")
                self.assertEqual(selected_us["currency"], "USD")
        for provider in (kr_pop, kr_val, us_pop, us_val):
            provider.assert_called_once()
        self.assertEqual(industry.call_count, 4)
        self.assertEqual(kr_popular[0]["name"], kr_value[0]["name"])
        self.assertEqual(us_popular[0]["name"], us_value[0]["name"])

    def test_kosdaq_market_type_overrides_name_guessing(self):
        kr = {"items": [{"itemCode": "247540", "price": {
            "itemName": "에코프로비엠", "marketType": "KOSDAQ",
            "krx": {"currentPrice": "100000"}
        }}]}
        with patch.object(rankings, "get_stock_industries", return_value={}), patch.object(
            rankings, "fetch_kr_popular_ranking_raw", return_value=kr,
        ):
            rankings.build_kr_popular_result()
        selected = rankings.get_market_selection("kr", "popular", "247540", "에코프로비엠")
        self.assertEqual(rankings.analysis_ticker_for_selection(selected), "247540.KQ")

    def test_wrong_market_menu_stock_code_or_name_is_rejected(self):
        rankings._remember_market_result("us", "popular", [{
            "name": "엔비디아", "symbol": "NVDA.O", "price": 200.0,
        }])
        self.assertIsNone(rankings.get_market_selection("kr", "popular", "NVDA.O"))
        self.assertIsNone(rankings.get_market_selection("us", "value", "NVDA.O"))
        self.assertIsNone(rankings.get_market_selection("us", "popular", "AAPL.O"))
        self.assertIsNone(rankings.get_market_selection("us", "popular", "NVDA.O", "테슬라"))
        self.assertIsNone(rankings.get_market_selection("us", "popular", "../bad"))
        self.assertIsNone(rankings.get_market_selection("us", "popular", "NVDA.O", ""))
        self.assertEqual(rankings.get_market_selection("us", "popular", "NVDA.O", "엔비디아")["price"], 200.0)

    def test_cached_menu_comparison_reuses_same_rows_without_source_calls(self):
        with patch.object(rankings, "fetch_us_popular_ranking_raw") as fetch:
            rankings._remember_market_result("us", "popular", [
                {"name": "엔비디아", "symbol": "NVDA.O", "rank": 1, "price": 225.78},
                {"name": "테슬라", "symbol": "TSLA.O", "rank": 2, "price": 401.0},
            ])
            rows = rankings.get_market_menu_rows("us", "popular")
            self.assertEqual(len(rows), 2)
            self.assertEqual([r["symbol"] for r in rows], ["NVDA.O", "TSLA.O"])
            rows[0]["price"] = 0
            self.assertEqual(rankings.get_market_menu_rows("us", "popular")[0]["price"], 225.78)
            self.assertEqual(rankings.get_market_menu_rows("kr", "popular"), [])
            fetch.assert_not_called()

    def test_older_menu_result_expires_without_fetching(self):
        with patch.object(rankings.time, "monotonic", return_value=100.0):
            rankings._remember_market_result("kr", "popular", [{
                "name": "삼성전자", "symbol": "005930",
            }])
        with patch.object(rankings.time, "monotonic", return_value=100.0 + rankings._SELECTION_TTL):
            self.assertIsNone(rankings.get_market_selection("kr", "popular", "005930"))

    def test_missing_exchange_does_not_guess_kospi_for_kosdaq(self):
        self.assertIsNone(rankings.analysis_ticker_for_selection({
            "market": "kr", "symbol": "247540", "market_type": "",
        }))
        self.assertIsNone(rankings.analysis_ticker_for_selection(None))


if __name__ == "__main__":
    unittest.main()
