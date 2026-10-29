"""US TOP20 trading-value regression after removal of unused Naver feeds.

Use an in-memory fake for psycopg: no external provider, Neon access, or writes.
"""
import os
import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from backend.providers import market_price
from backend.services import market_rankings
from backend.services import kiwoom_us_value_board as board


class MarketTradingValueTests(unittest.TestCase):
    def setUp(self):
        board._BOARD_CACHE.clear()

    def test_us_value_rows_only(self):
        captured_at = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = (7, captured_at)
        cursor.fetchall.return_value = [
            (1, "NVDA", "NVIDIA", "140.25", "1.23",
             "1230000000", 800000, "반도체", "NAS"),
            (2, "AAPL", "Apple", None, None,
             None, None, None, "NYS"),
        ]
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value = cursor
        pg = SimpleNamespace(connect=Mock(return_value=conn))
        with patch.dict(sys.modules, {"psycopg": pg}), \
             patch.dict(os.environ, {"NEWS_DATABASE_URL": "offline-test"}):
            rows = board._read_us_trading_value_board_uncached(limit=20)

        pg.connect.assert_called_once_with("offline-test", connect_timeout=4)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn("source='kiwoom'", cursor.execute.call_args_list[0].args[0])
        self.assertIn("ORDER BY e.rank ASC LIMIT %s", cursor.execute.call_args_list[1].args[0])
        self.assertEqual(cursor.execute.call_args_list[1].args[1], (7, 20))
        self.assertEqual(len(rows), 2)
        self.assertEqual([item["rank"] for item in rows], [1, 2])
        self.assertEqual(rows[0]["symbol"], "NVDA")
        self.assertEqual(rows[0]["source"], "kiwoom")
        self.assertEqual(rows[0]["price"], 140.25)
        self.assertEqual(rows[0]["change_pct"], 1.23)
        self.assertEqual(rows[0]["trading_value"], 1230000000.0)
        self.assertEqual(rows[0]["captured_at"], captured_at.isoformat())
        self.assertIsNone(rows[1]["price"])
        self.assertIsNone(rows[1]["trading_value"])

    def test_us_value_provider_keeps_cache_and_original_source(self):
        sample = [{"rank": 1, "symbol": "NVDA", "source": "kiwoom", "price": 140.25}]
        with patch.object(board, "_read_us_trading_value_board_uncached",
                          return_value=sample) as read, \
             patch.dict(os.environ, {"NEWS_DATABASE_URL": "offline-test"}):
            first = board.read_us_trading_value_board(limit=20)
            first[0]["price"] = 999
            second = board.read_us_trading_value_board(limit=20)
        read.assert_called_once()
        self.assertEqual(second[0]["price"], 140.25)
        self.assertEqual(second[0]["source"], "kiwoom")

    def test_removed_naver_ranking_collectors_are_absent(self):
        for module, names in [
            (market_price, [
                "fetch_kr_stock_quote", "fetch_kr_popular_ranking_raw",
                "fetch_kr_trading_value_ranking_raw", "fetch_us_popular_ranking_raw",
                "fetch_us_trading_value_ranking_raw", "MARKET_RANKING_CACHE",
            ]),
            (market_rankings, [
                "build_kr_popular_result", "build_kr_trading_value_result",
                "build_us_popular_result", "build_us_trading_value_result",
                "fetch_us_trading_value_ranking_raw",
            ]),
        ]:
            for name in names:
                with self.subTest(name=name):
                    self.assertFalse(hasattr(module, name))


if __name__ == "__main__":
    unittest.main()
