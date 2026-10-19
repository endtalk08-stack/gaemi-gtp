"""Offline one-day disclosure migration guardrails; no external API calls."""
import datetime as dt
import inspect
import os
import unittest
from unittest.mock import patch

from backend.services.disclosure_transfer import (
    _valid_identity, collect_once, one_day_filings, read_snapshot,
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

    def test_dart_one_day_window_uses_verified_time(self):
        now = dt.datetime(2026, 10, 20, 0, 0, tzinfo=dt.timezone.utc)
        rows = [
            {"receipt_datetime": "20261020", "report": "today"},
            {"receipt_datetime": "20261019", "time": "10:00", "report": "within24h"},
            {"receipt_datetime": "20261019", "time": "08:00", "report": "too_old"},
            {"receipt_datetime": "20261019", "report": "yesterday_time_unknown"},
            {"receipt_datetime": "20260920", "report": "30_day_old"},
        ]
        self.assertEqual(
            [row["report"] for row in one_day_filings(rows, "KR", now=now)],
            ["today", "within24h"],
        )

    def test_sec_one_day_uses_eastern_acceptance_time(self):
        now = dt.datetime(2026, 10, 20, 0, 0, tzinfo=dt.timezone.utc)
        rows = [
            {"acceptance_datetime": "2026-10-19T18:00:00", "date": "2026-10-19", "form": "4"},
            {"acceptance_datetime": "2026-10-18T18:00:00", "date": "2026-10-18", "form": "8-K"},
        ]
        self.assertEqual([r["form"] for r in one_day_filings(rows, "US", now=now)], ["4"])

    def test_temporary_only_no_30_day_query_or_archive(self):
        read_code = inspect.getsource(read_snapshot)
        collect_code = inspect.getsource(collect_once)
        self.assertIn("fetched_at > now() - interval '24 hours'", read_code)
        self.assertIn("DELETE FROM public.disclosure_snapshots", collect_code)
        self.assertIn("fetched_at <= now() - interval '24 hours'", collect_code)
        self.assertIn("ON CONFLICT (market, symbol) DO UPDATE", collect_code)
        self.assertIn("days=1", collect_code)
        self.assertNotIn("days=30", collect_code)
        self.assertNotIn("disclosure_history", collect_code)
        self.assertNotIn("interval '40 minutes'", read_code)


if __name__ == "__main__":
    unittest.main()
