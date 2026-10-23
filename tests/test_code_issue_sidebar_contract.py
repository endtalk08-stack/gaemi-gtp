"""Current database-backed sidebar contract, without legacy in-memory cache API."""
import os
import sys
import unittest
from unittest.mock import patch

from backend.services import market_issue_headlines as subject


class CodeIssueSidebarTests(unittest.TestCase):
    def test_us_renders_code_briefs_only(self):
        target = [{"name": "테슬라", "symbol": "TSLA"}]
        with patch.object(subject, "_read_worker_briefs", return_value={
            "테슬라": [{"headline": "테슬라, 설비투자 규모 축소", "summary": "기사 팩트", "stock_names": ["테슬라"]}]
        }):
            result = subject.get_market_issue_headlines("us", target)
        self.assertTrue(result["ok"])
        self.assertEqual(result["items"][0]["headline"], "테슬라, 설비투자 규모 축소")

    def test_missing_code_stays_unavailable(self):
        target = [{"name": "엔비디아", "symbol": "NVDA"}]
        with patch.object(subject, "_read_worker_briefs", return_value={}):
            result = subject.get_market_issue_headlines("us", target)
        self.assertEqual(result["items"][0]["status"], "unavailable")
        self.assertEqual(result["items"][0]["headline"], "")

    def test_sql_explicitly_prefers_code_channel(self):
        class Cursor:
            sql = ""
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def execute(self, sql, args):
                self.sql = sql
                self.args = args
            def fetchall(self):
                return [("테슬라", [{"headline": "코드 뉴스 팩트"}])]
        cursor = Cursor()
        class Conn:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def cursor(self): return cursor
        class Psycopg:
            @staticmethod
            def connect(*args, **kwargs): return Conn()
        with patch.dict(sys.modules, {"psycopg": Psycopg}), patch.dict(os.environ, {"NEWS_DATABASE_URL": "postgres://test"}):
            result = subject._read_worker_briefs("us", ["테슬라"])
        self.assertEqual(result["테슬라"][0]["headline"], "코드 뉴스 팩트")
        self.assertIn("_code_issue_briefs", cursor.sql)
        self.assertEqual(cursor.args[0], "미국")


if __name__ == "__main__":
    unittest.main()
