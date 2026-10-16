"""The central stock analysis and sidebar must prefer the same newest nonempty issues."""
import os
import sys
import types
import unittest
from unittest.mock import patch

from backend.services import news_result as subject
from backend.services import news_processed_results_store as store


def brief(headline):
    return [{"headline": headline, "summary": "기사 원문에 근거한 설명", "tags": []}]


def snapshot(headline):
    return {"_news_status": "ok", "paired_news_items": [], "storyboard_news_items": [],
            "issue_briefs": brief(headline) if headline else [], "keyword_storyboard": []}


class CentralNewsFreshnessTests(unittest.TestCase):
    def call(self, *, stored, worker, worker_newer):
        stored_rows = {store._key("미국", "엔비디아"): stored} if stored else {}
        with patch.object(store, "read_issue_briefs_batch", return_value=stored_rows), \
             patch.object(subject, "_read_worker_news_snapshot", return_value=(worker, worker_newer)), \
             patch.object(subject, "build_stock_news_result") as fallback:
            result = subject.get_shared_stock_news_result("엔비디아", market="미국")
            fallback.assert_not_called()
            return result

    def test_newer_digitalocean_issue_wins(self):
        result = self.call(stored=brief("AI 데이터센터 이슈"),
                           worker=snapshot("사업 제휴 이슈"), worker_newer=True)
        self.assertEqual(result["issue_briefs"][0]["headline"], "사업 제휴 이슈")

    def test_newer_central_issue_wins(self):
        result = self.call(stored=brief("최신 본문 이슈"),
                           worker=snapshot("이전 DO 이슈"), worker_newer=False)
        self.assertEqual(result["issue_briefs"][0]["headline"], "최신 본문 이슈")

    def test_empty_worker_does_not_erase_valid_central_issue(self):
        result = self.call(stored=brief("반도체 공급 부족 이슈"),
                           worker=snapshot(""), worker_newer=True)
        self.assertEqual(result["issue_briefs"][0]["headline"], "반도체 공급 부족 이슈")

    def test_worker_only_does_not_create_new_calls(self):
        result = self.call(stored=[], worker=snapshot("새로운 공급 계약"), worker_newer=True)
        self.assertEqual(result["issue_briefs"][0]["headline"], "새로운 공급 계약")

    def test_snapshot_read_compares_with_existing_saved_brief(self):
        seen = {}

        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def execute(self, query, args):
                seen["query"] = query
                seen["args"] = args
            def fetchone(self):
                return (snapshot("사업 제휴 이슈"), True)

        class Conn:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def cursor(self): return Cursor()

        with patch.dict(os.environ, {"NEWS_DATABASE_URL": "postgresql://placeholder"}), \
             patch.dict(sys.modules, {"psycopg": types.SimpleNamespace(
                 connect=lambda url, connect_timeout: Conn()
             )}):
            result = subject._read_worker_news_snapshot(
                "엔비디아", market="미국", limit=50, storyboard_limit=3,
                display_timezone="Asia/Seoul")
        self.assertEqual(result[0]["issue_briefs"][0]["headline"], "사업 제휴 이슈")
        self.assertTrue(result[1])
        self.assertIn("s.processed_at >= prev.created_at", seen["query"])
        self.assertIn("prev.result_type='stock_news_issue_briefs_v1'", seen["query"])
        self.assertEqual(seen["args"], ("us", "미국", "엔비디아", 50, 3, "Asia/Seoul"))


if __name__ == "__main__":
    unittest.main()
