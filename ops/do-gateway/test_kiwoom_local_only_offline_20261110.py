"""Offline regression of explicit single-source Kiwoom TOP20 local-only mode."""
from __future__ import annotations
import datetime as dt
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend import kiwoom_us_value_collector as collector

def complete_rows():
    return [{"rank": i, "symbol": "T%02d" % i, "name": "Test %d" % i, "exchange": "ND"}
            for i in range(1, 21)]

class Clock(dt.datetime):
    day = (2026, 11, 9, 13, 30)  # Monday NY business hours
    @classmethod
    def now(cls, tz=None):
        return dt.datetime(*cls.day, tzinfo=tz)

class TestLocalOnly(unittest.TestCase):
    def run_cli(self, argv, *, rows=None, date=(2026,11,9,13,30)):
        with patch.object(collector.dt, "datetime", Clock), \
             patch.object(collector, "fetch_us_trading_value_top", return_value=rows if rows is not None else complete_rows()) as fetch, \
             patch.object(collector, "_write_local_news_top20") as save, \
             patch.object(collector, "repair_saved_top20", side_effect=AssertionError("Neon repair")), \
             patch.object(sys, "argv", ["collector.py", *argv]), \
             patch.dict(os.environ, {"NEWS_DATABASE_URL": ""}):
            Clock.day = date
            outcome = collector.main()
            return outcome, fetch.call_count, save.call_count

    def test_local_only_collects_exactly_one_full_rank_no_db(self):
        rc, requests, writes = self.run_cli(["--local-news-top20"])
        self.assertEqual((rc, requests, writes), (0, 1, 1))

    def test_partial_rank_never_changes_saved_file(self):
        rc, requests, writes = self.run_cli(["--local-news-top20"], rows=complete_rows()[:19])
        self.assertEqual((rc, requests, writes), (3, 1, 0))

    def test_off_session_never_fetches_or_writes(self):
        rc, requests, writes = self.run_cli(["--local-news-top20"], date=(2026,11,7,13,30))
        self.assertEqual((rc, requests, writes), (0, 0, 0))

    def test_unknown_option_rejected_without_side_effects(self):
        with self.assertRaisesRegex(ValueError, "unsupported_collector_argument"):
            self.run_cli(["--not-local-news-top20"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
