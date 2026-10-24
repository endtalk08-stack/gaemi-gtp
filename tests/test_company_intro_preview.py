"""No-network tests for the single-stock narrative pilot."""
import os
import sys
import types
import unittest
from unittest.mock import patch

from backend.services.company_intro_preview import read_company_intro_preview, MICRON_INTRO


class FakeCursor:
    def __init__(self):
        self.queries = []
        self.calls = 0

    def execute(self, statement, params=None):
        self.queries.append((statement, params))
        assert statement.lstrip().startswith("SELECT")
        self.calls += 1

    def fetchone(self):
        return ("마이크론 테크놀로지", "반도체 및 반도체장비")

    def fetchall(self):
        return [
            ("AMD", "AMD"),
            ("AVGO", "브로드컴"),
            ("NVDA", "엔비디아"),
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor

    def cursor(self):
        return self.fake_cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class CompanyIntroTests(unittest.TestCase):
    def test_company_text_is_descriptive_not_quote_table(self):
        text = " ".join(MICRON_INTRO["paragraphs"])
        self.assertIn("메모리", text)
        self.assertIn("쉽게 말해", text)
        self.assertNotIn("현재가", text)
        self.assertNotIn("거래소:", text)

    def test_mu_only_reads_the_existing_sector_registry(self):
        cursor = FakeCursor()
        fake_psycopg = types.SimpleNamespace(connect=lambda *args, **kwargs: FakeConnection(cursor))
        with patch.dict(os.environ, {"NEWS_DATABASE_URL": "test"}, clear=False), patch.dict(sys.modules, {"psycopg": fake_psycopg}):
            result = read_company_intro_preview("mu")
        self.assertEqual(result["symbol"], "MU")
        self.assertEqual(result["name"], "마이크론 테크놀로지")
        self.assertEqual([x["symbol"] for x in result["related"]], ["AMD", "AVGO", "NVDA"])
        self.assertEqual(len(cursor.queries), 2)
        self.assertEqual(cursor.queries[1][1], ("반도체 및 반도체장비",))

    def test_unrelated_ticker_never_creates_unverified_description(self):
        self.assertIsNone(read_company_intro_preview("NVDA"))

    def test_missing_registry_configuration_fails_without_faking_company_data(self):
        with patch.dict(os.environ, {"NEWS_DATABASE_URL": ""}):
            with self.assertRaisesRegex(RuntimeError, "company_registry_unavailable"):
                read_company_intro_preview("MU")


if __name__ == "__main__":
    unittest.main()
