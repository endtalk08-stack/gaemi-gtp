"""Offline regression: disclosure identity no longer queries Neon US TOP20."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.services import disclosure_ranked_universe as registry


class DisclosureUniverseTests(unittest.TestCase):
    def test_existing_verified_identifiers_are_preserved_and_filtered(self):
        engine = SimpleNamespace(
            TICKERS={},
            DART_STOCK_CORP_CODES={"005930":"00126380", "000660":"00164779", "BAD":"00123456"},
            US_CIKS={"AAPL":"0000320193", "NVDA":"0001045810", "../bad":"0000123456", "TSLA":"invalid"},
        )
        self.assertEqual(registry.resolve_universe(engine), {
            "KR": ["000660", "005930"], "US": ["AAPL", "NVDA"],
        })

    def test_tracked_korean_symbol_uses_official_dart_mapping(self):
        engine = SimpleNamespace(
            TICKERS={"new":"123456.KS", "existing":"005930.KS", "ignored":"BTC-USD"},
            DART_STOCK_CORP_CODES={"005930":"00126380"},
            US_CIKS={},
            OPENDART_API_KEY="test-key",
        )
        with patch.object(registry, "_dart_corp_codes", return_value={"123456":"01234567"}) as lookup:
            result = registry.resolve_universe(engine)
        lookup.assert_called_once_with("test-key", {"123456"})
        self.assertEqual(result["KR"], ["005930", "123456"])

    def test_tracked_us_symbol_resolves_official_sec_directory_without_neon(self):
        engine = SimpleNamespace(
            TICKERS={"new":"NEWC", "existing":"BRK.B", "ignore":"BTC-USD"},
            DART_STOCK_CORP_CODES={},
            US_CIKS={"AAPL":"0000320193"},
            sec_filings=SimpleNamespace(_ticker_directory=lambda: {"NEWC":123456, "BRK.B":1067983}),
        )
        result = registry.resolve_universe(engine)
        self.assertEqual(result["US"], ["AAPL","BRK.B","NEWC"])
        self.assertEqual(engine.US_CIKS["NEWC"], "0000123456")

    def test_missing_db_does_not_affect_existing_disclosure_coverage(self):
        engine = SimpleNamespace(
            TICKERS={}, DART_STOCK_CORP_CODES={"005930":"00126380"},
            US_CIKS={"AAPL":"0000320193"},
        )
        self.assertEqual(registry.resolve_universe(engine), {
            "KR":["005930"], "US":["AAPL"],
        })


if __name__ == "__main__":
    unittest.main()
