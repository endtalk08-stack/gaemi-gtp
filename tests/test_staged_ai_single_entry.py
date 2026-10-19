"""Offline guards for one Groq entrypoint. Never connect to a real database or AI."""
import pathlib
import sys
import os
import unittest
from datetime import date, datetime
from unittest.mock import Mock, patch

OPS = pathlib.Path(__file__).resolve().parents[1] / "ops"
sys.path.insert(0, str(OPS))
import staged_auto_ai_daily as scheduled


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class SingleEntryTests(unittest.TestCase):
    def test_b_has_no_analyzer_or_paid_reservation(self):
        body = (OPS / "staged_auto_ai_daily.py").read_text()
        self.assertNotIn("run_stock_batch(", body)
        self.assertNotIn("analyze_news(", body)
        self.assertNotIn("reserve_once(", body)
        self.assertNotIn("GROQ_API_KEY", body)
        self.assertIn("reconcile_completed_ai_snapshots(conn, day)", body)

    def test_b_repairs_only_completed_paid_results(self):
        fake_db = Mock()
        fake_db.connect.return_value = FakeConnection()
        exchange_day = date(2026, 10, 19)
        with patch.object(scheduled, "due_exchange_day", return_value=exchange_day), \
             patch.dict(os.environ, {"NEWS_DATABASE_URL": "fake-db-for-offline-test", "GROQ_API_KEY": "fake-key"}), \
             patch.dict(sys.modules, {"psycopg": fake_db}), \
             patch.object(scheduled, "reconcile_completed_ai_snapshots", return_value=["TSMC ADR"]) as reconcile:
            self.assertEqual(scheduled.process_due_ai_snapshots(), 0)
            reconcile.assert_called_once()
            self.assertEqual(reconcile.call_args.args[1], exchange_day)
            fake_db.connect.assert_called_once()

    def test_b_before_schedule_does_not_connect(self):
        with patch.object(scheduled, "due_exchange_day", return_value=None), \
             patch.object(scheduled, "reconcile_completed_ai_snapshots") as repair:
            self.assertEqual(scheduled.process_due_ai_snapshots(), 0)
            repair.assert_not_called()

    def test_b_no_database_does_not_attempt_groq(self):
        with patch.object(scheduled, "due_exchange_day", return_value=date(2026, 10, 19)), \
             patch.dict(os.environ, {"NEWS_DATABASE_URL": "", "DATABASE_URL": ""}), \
             patch.object(scheduled, "reconcile_completed_ai_snapshots") as repair:
            self.assertEqual(scheduled.process_due_ai_snapshots(), 0)
            repair.assert_not_called()

    def test_recovery_query_never_creates_new_call(self):
        sql = scheduled._RECONCILE_DISPLAY_SQL
        self.assertIn("l.status='completed'", sql)
        self.assertIn("stock_ai_issue_sources_v1", sql)
        self.assertNotIn("INSERT INTO public.news_ai_call_ledger", sql)
        self.assertNotIn("DELETE FROM", sql)


if __name__ == "__main__":
    unittest.main()
