"""Offline Nasdaq plugin market-data/Neon issue marker contract."""
import datetime as dt
import unittest
from unittest.mock import patch

from backend.services import nasdaq_chart as chart


def bars():
    start = dt.date(2026, 9, 1)
    return [
        {"date": (start + dt.timedelta(days=i)).isoformat(), "close": 26000 + i * 5}
        for i in range(55)
    ]


def saved_marker(date, close=26265, tags=None):
    return {
        "nasdaq_chart_annotation": {
            "symbol": ".IXIC",
            "session_date_et": date,
            "close": close,
            "tags": tags or ["#나스닥상승", "#다우하락", "#실적호조"],
        }
    }


class TestNasdaqChart(unittest.TestCase):
    def test_tags_attach_to_exact_saved_trading_day(self):
        history = bars()
        day = history[-1]["date"]
        brief = saved_marker(day, history[-1]["close"])
        with patch.object(chart, "fetch_daily_price_history", return_value=history), \
             patch.object(chart, "read_brief", return_value=brief):
            result = chart.build_nasdaq_chart()
        self.assertEqual(result["symbol"], ".IXIC")
        self.assertEqual(len(result["points"]), len(history))
        self.assertEqual(result["annotation"]["session_date_et"], day)
        self.assertEqual(len(result["annotation"]["tags"]), 3)
        self.assertEqual(result["source"], "yahoo_daily")

    def test_wrong_day_and_wrong_index_closes_are_not_labelled(self):
        history = bars()
        test_values = [
            saved_marker("2025-01-01"),
            saved_marker(history[-1]["date"], close=15000),
        ]
        for data in test_values:
            with self.subTest(marker=data), \
                 patch.object(chart, "fetch_daily_price_history", return_value=history), \
                 patch.object(chart, "read_brief", return_value=data):
                self.assertIsNone(chart.build_nasdaq_chart()["annotation"])

    def test_expired_or_unavailable_brief_never_blocks_verified_history(self):
        for brief in (None, {}):
            with patch.object(chart, "fetch_daily_price_history", return_value=bars()), \
                 patch.object(chart, "read_brief", return_value=brief):
                result = chart.build_nasdaq_chart()
            self.assertEqual(len(result["points"]), 55)
            self.assertIsNone(result["annotation"])
        with patch.object(chart, "fetch_daily_price_history", return_value=bars()), \
             patch.object(chart, "read_brief", side_effect=OSError("Neon down")):
            self.assertIsNone(chart.build_nasdaq_chart()["annotation"])

    def test_unverified_quotes_are_removed_and_empty_data_is_unavailable(self):
        source = [
            {"date": "2026-10-19", "close": 100},
            {"date": "2026-10-20", "close": 0},
            {"date": "2026-10-20", "close": 105},
            {"date": "bad-date", "close": 115},
            {"date": "2026-10-22", "close": float("nan")},
            {"date": "2026-10-21", "close": 107},
        ]
        with patch.object(chart, "fetch_daily_price_history", return_value=source), \
             patch.object(chart, "read_brief", return_value=None):
            result = chart.build_nasdaq_chart()
        self.assertEqual([p["date"] for p in result["points"]],
                         ["2026-10-19", "2026-10-20", "2026-10-21"])
        with patch.object(chart, "fetch_daily_price_history", return_value=[]):
            self.assertIsNone(chart.build_nasdaq_chart())


if __name__ == "__main__":
    unittest.main()
