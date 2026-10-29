"""Offline regression: DART/SEC candidates do not need deleted ranking APIs."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.services import disclosure_ranked_universe as registry


BOARD = "backend.services.kiwoom_us_value_board.read_us_trading_value_board"


class DisclosureUniverseTests(unittest.TestCase):
    def test_existing_verified_identifiers_are_preserved_and_filtered(self):
        engine = SimpleNamespace(
            TICKERS={},
            DART_STOCK_CORP_CODES={
                "005930": "00126380", "000660": "00164779",
                "BAD": "00123456", "035420": "", "123456": "bad",
            },
            US_CIKS={
                "AAPL": "0000320193", "NVDA": "0001045810",
                "../bad": "0000123456", "TSLA": "invalid",
            },
        )
        with patch(BOARD, return_value=[]) as board:
            self.assertEqual(registry.resolve_universe(engine), {
                "KR": ["000660", "005930"],
                "US": ["AAPL", "NVDA"],
            })
        board.assert_called_once_with(limit=20)

    def test_tracked_korean_stock_is_resolved_using_official_dart_mapping(self):
        engine = SimpleNamespace(
            TICKERS={"new stock": "123456.KS", "existing": "005930.KS",
                     "invalid": "BTC-USD"},
            DART_STOCK_CORP_CODES={"005930": "00126380"},
            US_CIKS={},
            OPENDART_API_KEY="test-key",
        )
        with patch(BOARD, return_value=[]), patch.object(
            registry, "_dart_corp_codes", return_value={"123456": "01234567"}
        ) as lookup:
            result = registry.resolve_universe(engine)
        lookup.assert_called_once_with("test-key", {"123456"})
        self.assertEqual(result["KR"], ["005930", "123456"])
        self.assertEqual(engine.DART_STOCK_CORP_CODES["123456"], "01234567")

    def test_us_kiwoom_neon_top20_is_resolved_using_official_sec_directory(self):
        engine = SimpleNamespace(
            TICKERS={},
            DART_STOCK_CORP_CODES={},
            US_CIKS={"AAPL": "0000320193"},
            sec_filings=SimpleNamespace(_ticker_directory=lambda: {
                "NEWC": 123456, "BRK.B": 1067983, "INVALID": -10
            }),
        )
        rows = [
            {"symbol": "NEWC"}, {"symbol": "BRK.B"}, {"symbol": "INVALID"},
            {"symbol": "BAD!CODE"}, {"symbol": ""}, {"name": "not a symbol"},
        ]
        with patch(BOARD, return_value=rows) as board:
            result = registry.resolve_universe(engine)
        board.assert_called_once_with(limit=20)
        self.assertEqual(result["US"], ["AAPL", "BRK.B", "NEWC"])
        self.assertEqual(engine.US_CIKS["NEWC"], "0000123456")
        self.assertNotIn("INVALID", engine.US_CIKS)

    def test_database_offline_keeps_existing_disclosure_coverage(self):
        engine = SimpleNamespace(
            TICKERS={},
            DART_STOCK_CORP_CODES={"005930": "00126380"},
            US_CIKS={"AAPL": "0000320193"},
        )
        with patch(BOARD, return_value=None):
            self.assertEqual(registry.resolve_universe(engine), {
                "KR": ["005930"], "US": ["AAPL"],
            })

    def test_official_lookup_failure_keeps_existing_coverage(self):
        def failed_sec():
            raise ConnectionError("SEC offline")

        engine = SimpleNamespace(
            TICKERS={"new": "123456.KQ"},
            DART_STOCK_CORP_CODES={"005930": "00126380"},
            US_CIKS={"AAPL": "0000320193"},
            OPENDART_API_KEY="test",
            sec_filings=SimpleNamespace(_ticker_directory=failed_sec),
        )
        with patch(BOARD, return_value=[{"symbol": "NEWC"}]), patch.object(
            registry, "_dart_corp_codes", side_effect=ConnectionError("DART offline")
        ):
            self.assertEqual(registry.resolve_universe(engine), {
                "KR": ["005930"], "US": ["AAPL"],
            })


if __name__ == "__main__":
    unittest.main()
