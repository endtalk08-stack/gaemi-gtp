"""Offline fake-database tests; never connects to Neon or Groq."""
import importlib.util
import json
import pathlib
import unittest
from datetime import date

PATH = pathlib.Path(__file__).resolve().parents[1] / "ops" / "staged_daily_call_guard.py"
spec = importlib.util.spec_from_file_location("staged_daily_call_guard", PATH)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class FakeCursor:
    def __init__(self, database):
        self.database = database
        self.identity = None
        self.locked = False
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        if "pg_advisory_xact_lock" in query:
            self.locked = True
        elif query.lstrip().startswith("SELECT 1"):
            self.identity = tuple(params)
        elif query.lstrip().startswith("UPDATE"):
            key = tuple(params[4:7])
            record = self.database.get(key)
            self.rowcount = int(record is not None and record['hash'] == params[7] and record['status'] == 'reserved')
            if self.rowcount:
                record['status'] = params[0]
                record['result'] = params[1]
                record['failure_reason'] = params[3]
        elif query.lstrip().startswith("INSERT"):
            assert self.locked
            self.database[tuple(params[:3])] = {'hash': params[3], 'status': 'reserved'}
        else:
            raise AssertionError(query)

    def fetchone(self):
        return (1,) if self.identity in self.database else None


class FakeConnection:
    def __init__(self, database):
        self.database = database

    def cursor(self):
        return FakeCursor(self.database)


class DailyCallGuardTests(unittest.TestCase):
    def setUp(self):
        self.database = {}
        self.conn = FakeConnection(self.database)
        self.day = date(2026, 10, 17)

    def reserve(self, symbol="NVDA", day=None, hash_value="hash-a"):
        return guard.reserve_once(self.conn, market="US", symbol=symbol,
                                  exchange_day=day or self.day, request_hash=hash_value)

    def test_first_reservation_succeeds(self):
        self.assertTrue(self.reserve())

    def test_second_reservation_same_hash_blocked(self):
        self.assertTrue(self.reserve())
        self.assertFalse(self.reserve())

    def test_changed_news_hash_does_not_allow_second_call(self):
        self.assertTrue(self.reserve(hash_value="hash-a"))
        self.assertFalse(self.reserve(hash_value="hash-b"))

    def test_next_day_allowed(self):
        self.assertTrue(self.reserve())
        self.assertTrue(self.reserve(day=date(2026, 10, 18)))

    def test_different_stock_allowed(self):
        self.assertTrue(self.reserve())
        self.assertTrue(self.reserve(symbol="AMD"))

    def test_failure_status_keeps_daily_reservation(self):
        self.assertTrue(self.reserve())
        self.assertTrue(guard.finish_reservation(
            self.conn, market="US", symbol="NVDA", exchange_day=self.day,
            request_hash="hash-a", status="failed", failure_category="HTTPError",
            failure_reason="http_429"
        ))
        self.assertEqual(self.database[("US", "NVDA", self.day)]["failure_reason"], "http_429")
        self.assertFalse(self.reserve(hash_value="different-news"))

    def test_invalid_response_keeps_daily_reservation(self):
        self.assertTrue(self.reserve())
        self.assertTrue(guard.finish_reservation(
            self.conn, market="US", symbol="NVDA", exchange_day=self.day,
            request_hash="hash-a", status="invalid", failure_category="bad_json"
        ))
        self.assertFalse(self.reserve())

    def test_completed_zero_issues_keeps_daily_reservation(self):
        self.assertTrue(self.reserve())
        self.assertTrue(guard.finish_reservation(
            self.conn, market="US", symbol="NVDA", exchange_day=self.day,
            request_hash="hash-a", status="completed", result={"issues": []}
        ))
        self.assertFalse(self.reserve())

    def test_invalid_terminal_status_rejected(self):
        with self.assertRaises(ValueError):
            guard.finish_reservation(
                self.conn, market="US", symbol="NVDA", exchange_day=self.day,
                request_hash="hash-a", status="reserved"
            )

    def test_missing_reservation_cannot_be_completed(self):
        self.assertFalse(guard.finish_reservation(
            self.conn, market="US", symbol="NVDA", exchange_day=self.day,
            request_hash="missing", status="failed"
        ))

    def test_wrong_request_hash_cannot_finish(self):
        self.assertTrue(self.reserve())
        self.assertFalse(guard.finish_reservation(
            self.conn, market="US", symbol="NVDA", exchange_day=self.day,
            request_hash="wrong-hash", status="completed", result={"issues": []}
        ))

    def test_second_completion_is_rejected_by_db_status(self):
        self.assertTrue(self.reserve())
        self.assertTrue(guard.finish_reservation(self.conn, market="US", symbol="NVDA",
            exchange_day=self.day, request_hash="hash-a", status="completed", result={"issues": []}))
        self.assertFalse(guard.finish_reservation(self.conn, market="US", symbol="NVDA",
            exchange_day=self.day, request_hash="hash-a", status="completed", result={"issues": []}))
        self.assertEqual(json.loads(self.database[("US", "NVDA", self.day)]["result"]), {"issues": []})

    def test_bad_identity_rejected(self):
        with self.assertRaises(ValueError):
            guard.reserve_once(self.conn, market="US", symbol="", exchange_day=self.day, request_hash="x")


    def test_untrusted_failure_reason_is_not_written(self):
        self.assertTrue(self.reserve())
        with self.assertRaises(ValueError):
            guard.finish_reservation(
                self.conn, market="US", symbol="NVDA", exchange_day=self.day,
                request_hash="hash-a", status="failed",
                failure_reason="Authorization: private key")
        self.assertEqual(self.database[("US", "NVDA", self.day)]["status"], "reserved")


if __name__ == "__main__":
    unittest.main()
