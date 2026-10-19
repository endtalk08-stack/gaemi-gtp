"""Ranked disclosure symbols are resolved without altering the news worker."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from backend.services import disclosure_ranked_universe as registry


class DisclosureRankedUniverseTests(unittest.TestCase):
    def test_only_verified_ranked_identity_is_used(self):
        rows_kr = [{"symbol": "000660"}, {"symbol": "bad"}, {"symbol": "035420"}]
        rows_us = [{"symbol": "AAPL.O"}, {"symbol": "NEWC.N"}, {"symbol": "nonsense:12"}]
        with patch("backend.services.market_rankings.build_kr_popular_result", return_value=rows_kr), \
             patch("backend.services.market_rankings.build_kr_trading_value_result", return_value=[]), \
             patch("backend.services.market_rankings.build_us_popular_result", return_value=rows_us), \
             patch("backend.services.market_rankings.build_us_trading_value_result", return_value=[]):
            ranked = registry._ranked_symbols()
        self.assertEqual(ranked["KR"], {"000660", "035420"})
        self.assertEqual(ranked["US"], {"AAPL", "NEWC"})

    def test_ranked_extension_preserves_existing_known_stocks(self):
        engine = SimpleNamespace(
            DART_STOCK_CORP_CODES={"005930": "00126380"},
            US_CIKS={"AAPL": "0000320193"},
            OPENDART_API_KEY="test",
            sec_filings=SimpleNamespace(_ticker_directory=lambda: {"NEWC": 123456}),
        )
        with patch.object(registry, "_ranked_symbols", return_value={
            "KR": {"005930", "000660"}, "US": {"AAPL", "NEWC"}
        }), patch.object(registry, "_dart_corp_codes", return_value={"000660": "00164779"}):
            universe = registry.resolve_universe(engine)
        self.assertEqual(universe["KR"], ["000660", "005930"])
        self.assertEqual(universe["US"], ["AAPL", "NEWC"])
        self.assertEqual(engine.DART_STOCK_CORP_CODES["005930"], "00126380")
        self.assertEqual(engine.US_CIKS["NEWC"], "0000123456")


if __name__ == "__main__":
    unittest.main()
