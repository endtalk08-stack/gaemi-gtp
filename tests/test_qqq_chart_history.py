"""Offline regression checks for the read-only QQQ weekend chart fallback."""
import datetime
import unittest
from unittest.mock import patch

from backend.services import qqq_chart


class QqqChartHistoryTests(unittest.TestCase):
    def test_last_completed_daily_close_is_cached_and_kept_without_live_ticks(self):
        today = datetime.datetime.now(datetime.timezone.utc).date()
        days = [today - datetime.timedelta(days=n) for n in (5, 4, 3)]
        rows = [
            {"date": days[0].isoformat(), "close": 597.11},
            {"date": days[1].isoformat(), "close": 598.62},
            {"date": days[2].isoformat(), "close": 602.40},
        ]
        with patch.object(qqq_chart, "_CACHED_UNTIL", 0), \
             patch.object(qqq_chart, "_CACHED_RESULT", None), \
             patch.object(qqq_chart, "fetch_daily_price_history", return_value=rows) as loader:
            first = qqq_chart.read_qqq_daily_history()
            second = qqq_chart.read_qqq_daily_history()
        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        self.assertEqual(first["source"], "yahoo-daily")
        self.assertEqual(first["symbol"], "QQQ")
        self.assertEqual(first["close"], 602.40)
        self.assertEqual(len(first["points"]), 3)
        loader.assert_called_once_with("QQQ")

    def test_invalid_and_future_bars_are_discarded(self):
        today = datetime.datetime.now(datetime.timezone.utc).date()
        old1 = today - datetime.timedelta(days=6)
        old2 = today - datetime.timedelta(days=5)
        rows = [
            {"date": old1.isoformat(), "close": 600.0},
            {"date": old2.isoformat(), "close": 601.5},
            {"date": (today + datetime.timedelta(days=1)).isoformat(), "close": 9999},
            {"date": old2.isoformat(), "close": -4},
            {"date": "invalid", "close": 801},
        ]
        with patch.object(qqq_chart, "_CACHED_UNTIL", 0), \
             patch.object(qqq_chart, "_CACHED_RESULT", None), \
             patch.object(qqq_chart, "fetch_daily_price_history", return_value=rows):
            result = qqq_chart.read_qqq_daily_history()
        self.assertEqual(result["close"], 601.5)
        self.assertEqual(len(result["points"]), 2)

    def test_source_failure_has_no_fabricated_prices(self):
        with patch.object(qqq_chart, "_CACHED_UNTIL", 0), \
             patch.object(qqq_chart, "_CACHED_RESULT", None), \
             patch.object(qqq_chart, "fetch_daily_price_history", return_value=[]):
            self.assertIsNone(qqq_chart.read_qqq_daily_history())


if __name__ == "__main__":
    unittest.main()
