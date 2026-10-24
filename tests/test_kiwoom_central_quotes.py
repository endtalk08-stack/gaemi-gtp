"""No-network regression tests for the shared Kiwoom US sidebar/chat price."""
import unittest
from unittest.mock import patch

from backend.services.us_price_push import read_fresh_us_quote
from backend.services.stock_analysis import fetch_stock_price_result


class KiwoomCentralQuoteTests(unittest.TestCase):
    def test_returns_only_fresh_quote_for_exact_ticker(self):
        rows = [
            {"symbol": "MU", "price": 872.41, "change_pct": 1.86,
             "received_at_ms": 1000, "stale": False},
            {"symbol": "NVDA", "price": 212.2, "change_pct": -0.5,
             "received_at_ms": 1000, "stale": True},
        ]
        with patch("backend.services.us_price_push.read_memory_quotes", return_value=rows):
            self.assertEqual(read_fresh_us_quote("mu")["price"], 872.41)
            self.assertIsNone(read_fresh_us_quote("NVDA"))
            self.assertIsNone(read_fresh_us_quote("UNKNOWN"))
            self.assertIsNone(read_fresh_us_quote("../MU"))

    def test_central_quote_does_not_substitute_yahoo_close(self):
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
        self.assertIsNone(result["high_gap_pct"])
        self.assertIsNone(result["low_gap_pct"])
        self.assertEqual(result["historical_price_source"], "yahoo-daily")

    def test_central_day_high_low_uses_one_shared_kiwoom_tick(self):
        history = [{"date": "2026-10-22", "close": 108.0, "high": 111.0,
                    "low": 105.0, "volume": 200}]
        quote = {"symbol": "NVDA", "price": 110.0, "change_pct": 2.4,
                 "high": 112.0, "low": 102.0,
                 "received_at_ms": 121212, "stale": False}
        with patch("backend.services.stock_analysis.fetch_daily_price_history", return_value=history), \
             patch("backend.services.stock_analysis.read_fresh_us_quote", return_value=quote), \
             patch("backend.services.stock_analysis.read_recent_saved_us_quote",
                   side_effect=AssertionError("no second quote source")):
            result = fetch_stock_price_result(is_krw=False, ticker_symbol="NVDA")
        self.assertEqual(result["current_price"], quote["price"])
        self.assertEqual(result["quote_source"], "kiwoom-direct")
        self.assertAlmostEqual(result["high_gap_pct"], (110 / 112 - 1) * 100)
        self.assertAlmostEqual(result["low_gap_pct"], (110 / 102 - 1) * 100)
        self.assertIn("고가 -1.79%", result["first_reply_metrics_text"])
        self.assertIn("저가 +7.84%", result["first_reply_metrics_text"])

    def test_extended_hours_outside_reported_high_keeps_authentic_gap(self):
        # The FE trade can move beyond a previously reported session extreme.
        quote = {"symbol": "NVDA", "price": 115.0, "change_pct": 1.6,
                 "high": 112.0, "low": 101.0, "received_at_ms": 222, "stale": False}
        with patch("backend.services.stock_analysis.fetch_daily_price_history", return_value=[]), \
             patch("backend.services.stock_analysis.read_fresh_us_quote", return_value=quote):
            result = fetch_stock_price_result(is_krw=False, ticker_symbol="NVDA")
        self.assertAlmostEqual(result["high_gap_pct"], (115 / 112 - 1) * 100)

    def test_signed_relay_accepts_optional_fe_high_low_without_another_source(self):
        import json
        import time
        from backend.services import us_price_push as push
        now = time.time()
        payload = json.dumps({"sent_at_ms": int(now * 1000), "prices": [
            {"symbol": "NVDA", "price": 110.0, "change_pct": 2.4,
             "high": 112.0, "low": 102.0}
        ]}).encode("utf-8")
        with patch.object(push, "_verify_signature", return_value=True), \
             patch.object(push, "_LAST_SEND_MS", 0), patch.object(push, "_QUOTES", {}):
            ok, reason = push.accept_signed_quotes(payload, "0000000000", "mocked")
            self.assertEqual((ok, reason), (True, "accepted"))
            saved = push.read_fresh_us_quote("NVDA")
            self.assertEqual((saved["price"], saved["high"], saved["low"]), (110., 112., 102.))
            invalid = json.dumps({"sent_at_ms": int(now * 1000) + 1, "prices": [
                {"symbol": "NVDA", "price": 110.0, "change_pct": 2.4,
                 "high": 102.0, "low": 112.0}
            ]}).encode("utf-8")
            self.assertEqual(push.accept_signed_quotes(invalid, "0000000000", "mocked")[1],
                             "invalid_payload")

    def test_missing_tick_not_replaced_with_yahoo_previous_close(self):
        history = [
            {"date": "2026-10-21", "close": 855.0, "high": 860.0, "low": 850.0, "volume": 200},
            {"date": "2026-10-22", "close": 856.49, "high": 860.0, "low": 840.0, "volume": 200},
        ]
        with patch("backend.services.stock_analysis.fetch_daily_price_history", return_value=history), \
             patch("backend.services.stock_analysis.read_fresh_us_quote", return_value=None), \
             patch("backend.services.stock_analysis.read_recent_saved_us_quote", return_value=None):
            result = fetch_stock_price_result(is_krw=False, ticker_symbol="MU")
        self.assertEqual(result["current_price"], 0)
        self.assertEqual(result["quote_source"], "kiwoom-unavailable")
        self.assertEqual(result["price_text"], "시세 조회 실패")
        self.assertNotIn("현재 주가는 $856.49", result["first_reply_metrics_text"])

    def test_missing_change_is_not_derived_from_old_yahoo_close(self):
        with patch("backend.services.stock_analysis.fetch_daily_price_history", return_value=[]), \
             patch("backend.services.stock_analysis.read_fresh_us_quote",
                   return_value={"price": 872.41, "change_pct": None, "received_at_ms": 1}):
            result = fetch_stock_price_result(is_krw=False, ticker_symbol="MU")
        self.assertEqual(result["current_price"], 872.41)
        self.assertEqual(result["change_pct"], 0.0)
        self.assertEqual(result["quote_source"], "kiwoom-direct")



    def test_missing_live_tick_uses_labeled_recent_saved_kiwoom_price(self):
        saved = {"symbol": "MU", "price": 877.55, "change_pct": 2.46,
                 "received_at_ms": 9999, "stale": True}
        with patch("backend.services.stock_analysis.fetch_daily_price_history", return_value=[]), \
             patch("backend.services.stock_analysis.read_fresh_us_quote", return_value=None), \
             patch("backend.services.stock_analysis.read_recent_saved_us_quote", return_value=saved):
            result = fetch_stock_price_result(is_krw=False, ticker_symbol="MU")
        self.assertEqual(result["current_price"], 877.55)
        self.assertEqual(result["quote_source"], "kiwoom-neon-snapshot")
        self.assertEqual(result["quote_received_at_ms"], 9999)

    def test_saved_quote_rejects_expired_or_bad_source(self):
        from datetime import datetime, timedelta, timezone
        from backend.services.kiwoom_us_value_board import read_recent_saved_us_quote
        now = datetime.now(timezone.utc)
        with patch("backend.services.kiwoom_us_value_board.read_us_trading_value_board",
                   return_value=[{"symbol": "MU", "price": 877.55, "change_pct": 2.46,
                                  "captured_at": (now-timedelta(hours=4)).isoformat()}]):
            self.assertEqual(read_recent_saved_us_quote("MU")["price"], 877.55)
            self.assertIsNone(read_recent_saved_us_quote("NVDA"))
        with patch("backend.services.kiwoom_us_value_board.read_us_trading_value_board",
                   return_value=[{"symbol": "MU", "price": 877.55, "change_pct": 2.46,
                                  "captured_at": (now-timedelta(hours=80)).isoformat()}]):
            self.assertIsNone(read_recent_saved_us_quote("MU"))

if __name__ == "__main__":
    unittest.main()
