"""Disclosure collection uses verified known IDs, without a ranking API call."""
import unittest
from types import SimpleNamespace
from backend.services.disclosure_ranked_universe import resolve_universe


class VerifiedDisclosureUniverseTests(unittest.TestCase):
    def test_only_verified_local_dart_and_sec_identifiers(self):
        source = SimpleNamespace(
            DART_STOCK_CORP_CODES={
                "005930": "00126380", "000660": "00164779",
                "BAD": "00123456", "035420": "", "123456": "bad",
            },
            US_CIKS={
                "AAPL": "0000320193", "NVDA": "0001045810",
                "../bad": "0000123456", "TSLA": "invalid",
            },
        )
        self.assertEqual(resolve_universe(source), {
            "KR": ["000660", "005930"],
            "US": ["AAPL", "NVDA"],
        })

    def test_missing_mapping_never_requests_new_market_rankings(self):
        source = SimpleNamespace(DART_STOCK_CORP_CODES={}, US_CIKS={})
        self.assertEqual(resolve_universe(source), {"KR": [], "US": []})


if __name__ == "__main__":
    unittest.main()
