"""Pure tests of Neon-only disclosure view; no network or external APIs."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from backend.services.disclosure_snapshot_reader import _filing_datetime, read_disclosure_snapshot


class _Cursor:
    def __init__(self, result):
        self.result = result
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, statement, params):
        assert "interval '30 days'" in statement
        assert params == ("US", "AAPL")
    def fetchone(self):
        return self.result


class _Conn:
    def __init__(self, result):
        self.result = result
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def cursor(self):
        return _Cursor(self.result)


class DisclosureSnapshotReaderTests(unittest.TestCase):
    def test_date_formats(self):
        self.assertEqual(_filing_datetime({"receipt_datetime": "20261019"}).date().isoformat(), "2026-10-19")
        self.assertEqual(_filing_datetime({"acceptance_datetime": "2026-10-17T00:29:07.000Z"}).date().isoformat(), "2026-10-17")
        self.assertIsNone(_filing_datetime({"date": "10/19"}))

    def test_missing_credentials_never_fetches(self):
        with patch.dict("os.environ", {"NEWS_DATABASE_URL": ""}):
            self.assertIsNone(read_disclosure_snapshot("US", "AAPL"))

    def test_snapshot_trims_expired_filing(self):
        import sys
        from types import SimpleNamespace
        fake = SimpleNamespace(connect=lambda *a, **kw: _Conn(([
            {"date": "2026-10-19", "form": "8-K"},
            {"date": "2026-09-01", "form": "10-Q"},
        ],)))
        with patch.dict("os.environ", {"NEWS_DATABASE_URL": "fake://db"}), patch.dict(sys.modules, {"psycopg": fake}):
            result = read_disclosure_snapshot("US", "AAPL", now=datetime(2026, 10, 19, tzinfo=timezone.utc))
        self.assertEqual([record["form"] for record in result], ["8-K"])

    def test_invalid_identity_no_db_access(self):
        with patch.dict("os.environ", {"NEWS_DATABASE_URL": "fake://db"}):
            self.assertIsNone(read_disclosure_snapshot("US", "../bad"))


if __name__ == "__main__":
    unittest.main()
