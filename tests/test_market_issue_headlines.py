"""Sidebar titles must exactly reuse the central news issue briefs stored for 24h."""
import unittest
from unittest.mock import patch

from backend.services import market_issue_headlines as subject
from backend.services import news_processed_results_store as store


class MarketIssueHeadlineTests(unittest.TestCase):
    def setUp(self):
        with subject._ISSUE_LOCK:
            jobs = list(set(subject._ISSUE_PENDING.values()))
        for future in jobs:
            future.result(timeout=5)
        with subject._ISSUE_LOCK:
            subject._ISSUE_CACHE.clear()
            subject._ISSUE_PENDING.clear()

    def _await_jobs(self):
        with subject._ISSUE_LOCK:
            jobs = set(subject._ISSUE_PENDING.values())
        for job in jobs:
            job.result(timeout=5)

    def test_cached_central_brief_title_displays_without_analysis(self):
        items = [{"name": "삼성전자", "symbol": "005930"}]
        summary = "삼성전자와 SK하이닉스가 AI 반도체 수요에 대응한다."
        payload = [{"headline": "AI 반도체 이슈", "summary": summary,
                    "tags": ["AI반도체", "공장증설"]}]
        with patch.object(subject, "read_issue_briefs_batch", return_value={
            store._key("kr", "삼성전자"): payload
        }) as reader, patch.object(subject, "get_shared_stock_news_result") as generator:
            result = subject.get_market_issue_headlines("kr", items)
        self.assertEqual(result["items"][0]["headline"], payload[0]["headline"])
        self.assertEqual(result["items"][0]["status"], "ready")
        self.assertFalse(result["pending"])
        reader.assert_called_once()
        generator.assert_not_called()

    def test_twenty_stocks_use_existing_shared_analysis_when_missing(self):
        items = [{"name": f"종목{i}", "symbol": f"{i:06d}"} for i in range(20)]

        def build(name, **kwargs):
            return {"_news_status": "ok", "issue_briefs": [
                {"headline": f"{name} AI 반도체 이슈", "summary": "뉴스 근거 설명"}
            ]}

        with patch.object(subject, "read_issue_briefs_batch", return_value={}) as reader, \
             patch.object(subject, "get_shared_stock_news_result", side_effect=build) as builder:
            initial = subject.get_market_issue_headlines("kr", items)
            self.assertTrue(initial["pending"])
            self._await_jobs()
            ready = subject.get_market_issue_headlines("kr", items)
            self.assertFalse(ready["pending"])
            self.assertEqual(len([x for x in ready["items"] if x["status"] == "ready"]), 20)
            self.assertEqual(builder.call_count, 20)
            reader.assert_called_once()

    def test_missing_verified_issue_is_not_fabricated(self):
        items = [{"name": "삼성SDI", "symbol": "006400"}]
        with patch.object(subject, "read_issue_briefs_batch", return_value={}), \
             patch.object(subject, "get_shared_stock_news_result",
                          return_value={"_news_status": "ok", "issue_briefs": []}):
            subject.get_market_issue_headlines("kr", items)
            self._await_jobs()
            result = subject.get_market_issue_headlines("kr", items)
        self.assertEqual(result["items"][0]["status"], "unavailable")
        self.assertEqual(result["items"][0]["headline"], "")

    def test_saved_content_is_only_the_displayed_brief(self):
        original = [{"headline": "AI 반도체 이슈",
                     "summary": "기사에서 검증한 설명입니다.",
                     "tags": ["반도체", "수요증가"],
                     "stock_names": ["삼성전자"],
                     "time": "06:04",
                     "full_article_body": "DO NOT STORE"}]
        selected = store._briefs_for_storage(original)
        self.assertEqual(selected[0]["headline"], "AI 반도체 이슈")
        self.assertEqual(selected[0]["summary"], "기사에서 검증한 설명입니다.")
        self.assertEqual(selected[0]["tags"], ["반도체", "수요증가"])
        self.assertNotIn("full_article_body", selected[0])

    def test_bad_symbol_and_oversized_list_rejected(self):
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines("kr", [{"name": "SK", "symbol": "NVDA"}])
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [{"name": "x", "symbol": "005930"}] * 21,
            )
