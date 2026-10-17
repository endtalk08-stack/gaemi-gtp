"""Offline persistence checks: no Neon writes or AI calls."""
from datetime import date
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops"))
from staged_ai_issue_store import save_ai_issues


class Cursor:
    def __init__(self):
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, query, params):
        self.calls.append((query, params))
    def fetchone(self):
        return (100 + len(self.calls),)


class Conn:
    def __init__(self):
        self.cur = Cursor()
        self.transactions = 0
    def cursor(self):
        return self.cur
    def transaction(self):
        self.transactions += 1
        return self
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class StoreTests(unittest.TestCase):
    def test_zero_issues_no_connection_needed(self):
        self.assertEqual(save_ai_issues(None, [], market="US", symbol="NVDA",
                                        exchange_day=date(2026, 10, 17)), [])

    def test_two_issues_existing_connection(self):
        conn = Conn()
        issues = [
            {"headline": "수요", "summary": "수요 확대", "tags": ["#수요"]},
            {"headline": "투자", "summary": "투자 확대", "tags": ["#투자"]},
        ]
        result = save_ai_issues(conn, issues, market="KR", symbol="005930",
                                exchange_day=date(2026, 10, 17))
        self.assertEqual(result, [101, 102])
        self.assertEqual(conn.transactions, 1)
        self.assertEqual(len(conn.cur.calls), 2)
        self.assertIn("news_ai_issues", conn.cur.calls[0][0])
        self.assertIn('"#수요"', conn.cur.calls[0][1][5])

    def test_reject_missing_connection(self):
        with self.assertRaises(ValueError):
            save_ai_issues(None, [{"headline": "제목", "summary": "내용", "tags": []}],
                           market="US", symbol="NVDA", exchange_day=date(2026, 10, 17))


if __name__ == "__main__":
    unittest.main()
