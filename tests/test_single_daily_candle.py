"""One-candle UI data: reuse existing daily series, no duplicate quote provider call."""
import datetime
import io
import json
import unittest
from unittest.mock import patch

from backend.providers import market_price
from backend.services.stock_analysis import _latest_daily_candle, fetch_stock_price_result


class SingleDailyCandleTests(unittest.TestCase):
    def setUp(self):
        market_price.DAILY_HISTORY_CACHE.clear()

    def tearDown(self):
        market_price.DAILY_HISTORY_CACHE.clear()

    def test_yahoo_open_is_preserved_from_existing_daily_response(self):
        stamps = [
            int(datetime.datetime(2026, 10, day, 16, tzinfo=datetime.timezone.utc).timestamp())
            for day in (21, 22)
        ]
        response = {
            "chart": {"result": [{
                "timestamp": stamps,
                "meta": {"exchangeTimezoneName": "America/New_York"},
                "indicators": {"quote": [{
                    "open": [98.0, 101.0],
                    "high": [103.0, 110.0],
                    "low": [97.0, 100.0],
                    "close": [100.0, 106.0],
                    "volume": [100, 200]
                }]}
            }]}
        }
        blob = io.BytesIO(json.dumps(response).encode("utf-8"))
        with patch.object(market_price.urllib.request, "urlopen", return_value=blob) as api:
            rows = market_price.fetch_daily_price_history("MU")
            self.assertEqual(rows[1]["open"], 101.0)
            self.assertEqual(rows[1]["date"], "2026-10-22")
            self.assertEqual(
                _latest_daily_candle(rows, is_krw=False,
                                     as_of_date=datetime.date(2026, 10, 23))["change_pct"],
                6.0
            )
            market_price.fetch_daily_price_history("MU")
            api.assert_called_once()

    def test_candle_uses_its_own_close_not_realtime_kiwoom(self):
        history = [
            {"date": "2026-10-21", "open": 98, "high": 103, "low": 97, "close": 100},
            {"date": "2026-10-22", "open": 101, "high": 110, "low": 100, "close": 106},
        ]
        quote = {"symbol": "MU", "price": 109.0, "change_pct": 2.83,
                 "received_at_ms": 11111, "stale": False}
        with patch("backend.services.stock_analysis.fetch_daily_price_history",
                   return_value=history), patch(
            "backend.services.stock_analysis.read_fresh_us_quote", return_value=quote
        ):
            result = fetch_stock_price_result(is_krw=False, ticker_symbol="MU")
        self.assertEqual(result["current_price"], 109)
        self.assertEqual(result["change_pct"], 2.83)
        self.assertEqual(result["daily_candle"]["change_pct"], 6.0)
        self.assertEqual(result["daily_candle"]["close"], 106.0)

    def test_no_fabricated_candle_without_open_previous_or_valid_date(self):
        today = datetime.date(2026, 10, 23)
        valid = {"date": "2026-10-22", "open": 101, "high": 110,
                 "low": 100, "close": 106}
        prev = {"date": "2026-10-21", "close": 100}
        self.assertIsNone(_latest_daily_candle([prev], is_krw=False, as_of_date=today))
        self.assertIsNone(_latest_daily_candle(
            [prev, {k: v for k, v in valid.items() if k != "open"}],
            is_krw=False, as_of_date=today
        ))
        self.assertIsNone(_latest_daily_candle(
            [prev, {**valid, "high": 104}],
            is_krw=False, as_of_date=today
        ))
        self.assertIsNone(_latest_daily_candle(
            [prev, {**valid, "date": "2026-10-24"}],
            is_krw=False, as_of_date=today
        ))

    def test_stale_bar_is_suppressed_without_faking_today(self):
        bars = [
            {"date": "2026-10-01", "close": 100},
            {"date": "2026-10-02", "open": 101, "high": 110,
             "low": 100, "close": 106},
        ]
        self.assertIsNone(_latest_daily_candle(
            bars, is_krw=False, as_of_date=datetime.date(2026, 10, 23)
        ))


if __name__ == "__main__":
    unittest.main()
