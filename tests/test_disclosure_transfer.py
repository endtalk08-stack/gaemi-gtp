"""Offline disclosure-only migration guardrails; no external API calls."""
import os
import unittest
from unittest.mock import patch

from backend.services.disclosure_transfer import (
    _valid_identity, collect_once, read_snapshot,
)


class DisclosureTransferTests(unittest.TestCase):
    def test_identity_limits_are_strict(self):
        self.assertEqual(_valid_identity("kr", "005930"), ("KR", "005930"))
        self.assertEqual(_valid_identity("us", "AAPL"), ("US", "AAPL"))
        for market, symbol in [("KR", "NVDA"), ("US", "005930"), ("US", "../../etc/passwd")]:
            with self.subTest(market=market, symbol=symbol):
                with self.assertRaises(ValueError):
                    _valid_identity(market, symbol)

    def test_off_by_default_does_not_access_db(self):
        with patch.dict(os.environ, {"NEWS_DATABASE_URL": ""}):
            self.assertIsNone(read_snapshot("KR", "005930"))
            self.assertIsNone(read_snapshot("US", "AAPL"))

    def test_do_collector_requires_neon_before_provider_call(self):
        with patch.dict(os.environ, {"NEWS_DATABASE_URL": ""}):
            with self.assertRaisesRegex(RuntimeError, "disclosure_db_missing"):
                collect_once("US", "AAPL")


if __name__ == "__main__":
    unittest.main()
