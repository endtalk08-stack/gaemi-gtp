"""Sidebar must prefer a newer verified DO title, not an older 24h Render brief."""
import os
import sys
import types
import unittest
from unittest.mock import patch

from backend.services import market_issue_headlines as subject
from backend.services.news_processed_results_store import _key


def brief(headline):
    return [{"headline": headline, "summary": "검증된 기사 원문에 근거한 이슈"}]


class SidebarIssueFreshnessTests(unittest.TestCase):
    def test_newer_do_title_wins_over_existing_old_title(self):
        old = {_key("us", "엔비디아"): brief("AI 데이터센터 이슈")}
        newer = {"엔비디아": brief("사업 제휴 이슈")}
        rows = [{"name": "엔비디아", "symbol": "NVDA.O"}]
        with patch.object(subject, "read_issue_briefs_batch", return_value=old), \
             patch.object(subject, "_read_worker_briefs", return_value=newer) as reader:
            result = subject.get_market_issue_headlines("us", rows)
        self.assertEqual(result["items"][0]["headline"], "사업 제휴 이슈")
        self.assertEqual(result["items"][0]["status"], "ready")
        reader.assert_called_once_with("us", ["엔비디아"])

    def test_existing_title_wins_if_worker_is_older_or_missing(self):
        old = {_key("us", "엔비디아"): brief("최근 본문 이슈")}
        rows = [{"name": "엔비디아", "symbol": "NVDA.O"}]
        with patch.object(subject, "read_issue_briefs_batch", return_value=old), \
             patch.object(subject, "_read_worker_briefs", return_value={}):
            result = subject.get_market_issue_headlines("us", rows)
        self.assertEqual(result["items"][0]["headline"], "최근 본문 이슈")

    def test_empty_newer_worker_does_not_delete_existing_title(self):
        old = {_key("us", "애플"): brief("반도체 공급 부족 이슈")}
        rows = [{"name": "애플", "symbol": "AAPL.O"}]
        with patch.object(subject, "read_issue_briefs_batch", return_value=old), \
             patch.object(subject, "_read_worker_briefs", return_value={"애플": []}):
            result = subject.get_market_issue_headlines("us", rows)
        self.assertEqual(result["items"][0]["headline"], "반도체 공급 부족 이슈")

    def test_no_issue_is_not_fabricated_and_no_analysis_runs(self):
        rows = [{"name": "테슬라", "symbol": "TSLA.O"}]
        with patch.object(subject, "read_issue_briefs_batch", return_value={}), \
             patch.object(subject, "_read_worker_briefs", return_value={}):
            result = subject.get_market_issue_headlines("us", rows)
        self.assertEqual(result["items"][0]["status"], "unavailable")
        self.assertEqual(result["items"][0]["headline"], "")
        self.assertFalse(result["pending"])

    def test_worker_query_limits_to_newer_expiring_snapshots(self):
        seen = {}

        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def execute(self, query, args):
                seen["query"] = query
                seen["args"] = args
            def fetchall(self):
                return [("엔비디아", brief("사업 제휴 이슈"))]

        class Connection:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def cursor(self): return Cursor()

        with patch.dict(os.environ, {"NEWS_DATABASE_URL": "postgresql://placeholder"}), \
             patch.dict(sys.modules, {"psycopg": types.SimpleNamespace(
                 connect=lambda url, connect_timeout: Connection()
             )}):
            result = subject._read_worker_briefs("us", ["엔비디아"])
        self.assertEqual(result["엔비디아"][0]["headline"], "사업 제휴 이슈")
        self.assertIn("s.processed_at >= prev.created_at", seen["query"])
        self.assertIn("prev.result_type='stock_news_issue_briefs_v1'", seen["query"])
        self.assertIn("s.expires_at>now()", seen["query"])
        self.assertEqual(seen["args"], ("us", "미국", ["엔비디아"]))


if __name__ == "__main__":
    unittest.main()
