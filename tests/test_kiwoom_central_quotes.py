"""No-network regression tests for the shared DigitalOcean Kiwoom analysis quote."""
import time
import unittest
from unittest.mock import patch

from backend import kiwoom_us_top20_api as quote_api
from backend.services.stock_analysis import fetch_stock_price_result


class KiwoomCentralQuoteTests(unittest.TestCase):
    def test_reads_only_a_fresh_quote_from_the_do_process_cache(self):
        now_ms = int(time.time() * 1000)
        row = {"symbol": "MU", "price": 872.41, "change_pct": 1.86,
               "received_at_ms": now_ms, "stale": False}
        with patch.object(quote_api, "_TOP20_QUOTES", {"MU": row}), \
             patch.object(quote_api, "_INDUSTRY_QUOTES", {}), \
             patch.object(quote_api, "_ETF_QUOTES", {}), \
             patch.object(quote_api, "_MARKET_WIDGET_QUOTES", {}), \
             patch.object(quote_api, "_us_close_get", return_value=None):
            result = quote_api.read_fresh_us_quote("mu")
        self.assertEqual(result["price"], 872.41)
        self.assertEqual(result["change_pct"], 1.86)
        self.assertFalse(result["stale"])

    def test_stale_or_unknown_quote_is_not_presented_as_live(self):
        old = int(time.time() * 1000) - 60000
        row = {"symbol": "MU", "price": 872.41, "change_pct": 1.86,
               "received_at_ms": old, "stale": True}
        with patch.object(quote_api, "_TOP20_QUOTES", {"MU": row}), \
             patch.object(quote_api, "_INDUSTRY_QUOTES", {}), \
             patch.object(quote_api, "_ETF_QUOTES", {}), \
             patch.object(quote_api, "_MARKET_WIDGET_QUOTES", {}), \
             patch.object(quote_api, "_us_close_get", return_value=None):
            self.assertIsNone(quote_api.read_fresh_us_quote("MU"))
            self.assertIsNone(quote_api.read_fresh_us_quote("UNKNOWN"))
            self.assertIsNone(quote_api.read_fresh_us_quote("../MU"))

    def test_analysis_uses_do_quote_cache_without_an_external_relay(self):
        history = [
            {"date": "2026-10-21", "close": 855.0, "high": 860.0, "low": 850.0, "volume": 200},
            {"date": "2026-10-22", "close": 856.49, "high": 860.0, "low": 840.0, "volume": 200},
        ]
        quote = {"symbol": "MU", "price": 872.41, "change_pct": 1.86,
                 "received_at_ms": 11111, "stale": False}
        with patch("backend.services.stock_analysis.fetch_daily_price_history", return_value=history), \
             patch("backend.services.stock_analysis.read_fresh_us_quote", return_value=quote):
            result = fetch_stock_price_result(is_krw=False, ticker_symbol="MU")
        self.assertEqual(result["current_price"], 872.41)
        self.assertEqual(result["change_pct"], 1.86)
        self.assertEqual(result["quote_source"], "kiwoom-direct")
        self.assertEqual(result["quote_received_at_ms"], 11111)
        self.assertEqual(result["historical_price_source"], "yahoo-daily")

    def test_missing_tick_is_not_replaced_with_yahoo_previous_close(self):
        history = [
            {"date": "2026-10-21", "close": 855.0, "high": 860.0, "low": 850.0, "volume": 200},
            {"date": "2026-10-22", "close": 856.49, "high": 860.0, "low": 840.0, "volume": 200},
        ]
        with patch("backend.services.stock_analysis.fetch_daily_price_history", return_value=history), \
             patch("backend.services.stock_analysis.read_fresh_us_quote", return_value=None):
            result = fetch_stock_price_result(is_krw=False, ticker_symbol="MU")
        self.assertEqual(result["current_price"], 0)
        self.assertEqual(result["quote_source"], "kiwoom-unavailable")
        self.assertEqual(result["price_text"], "시세 조회 실패")
        self.assertNotIn("현재 주가는 $856.49", result["first_reply_metrics_text"])


if __name__ == "__main__":
    unittest.main()
