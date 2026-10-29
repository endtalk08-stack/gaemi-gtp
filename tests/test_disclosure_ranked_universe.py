"""Disclosure identifiers remain independent of removed Naver ranking APIs."""
import unittest
from types import SimpleNamespace

from backend.services.disclosure_ranked_universe import resolve_universe


class DisclosureIdentityTests(unittest.TestCase):
    def test_only_existing_verified_company_mappings_are_used(self):
        engine = SimpleNamespace(
            DART_STOCK_CORP_CODES={
                "005930": "00126380",
                "000660": "00164779",
                "BAD": "00164779",
                "035420": "not-a-corp-code",
            },
            US_CIKS={
                "NVDA": "0001045810",
                "AAPL": "0000320193",
                "../bad": "0001045810",
                "NEWC": "unverified",
            },
        )
        result = resolve_universe(engine)
        self.assertEqual(result["KR"], ["000660", "005930"])
        self.assertEqual(result["US"], ["AAPL", "NVDA"])

    def test_no_ranking_fetch_or_mutation(self):
        engine = SimpleNamespace(
            DART_STOCK_CORP_CODES={"005930": "00126380"},
            US_CIKS={"AAPL": "0000320193"},
        )
        before_kr = dict(engine.DART_STOCK_CORP_CODES)
        before_us = dict(engine.US_CIKS)
        self.assertEqual(resolve_universe(engine), {
            "KR": ["005930"], "US": ["AAPL"],
        })
        self.assertEqual(before_kr, engine.DART_STOCK_CORP_CODES)
        self.assertEqual(before_us, engine.US_CIKS)


if __name__ == "__main__":
    unittest.main()
