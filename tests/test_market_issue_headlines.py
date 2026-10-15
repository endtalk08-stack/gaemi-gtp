"""Sidebar titles reuse 24h processed results and existing raw metadata."""
import unittest
from unittest.mock import patch

from backend.services import market_issue_headlines as subject


class MarketIssueHeadlineTests(unittest.TestCase):
    def setUp(self):
        with subject._ISSUE_LOCK:
            futures = list(set(subject._ISSUE_PENDING.values()))
        for future in futures:
            future.result(timeout=5)
        with subject._ISSUE_LOCK:
            subject._ISSUE_CACHE.clear()
            subject._ISSUE_PENDING.clear()

    def _await_jobs(self):
        with subject._ISSUE_LOCK:
            jobs = set(subject._ISSUE_PENDING.values())
        for job in jobs:
            job.result(timeout=5)

    def test_previously_processed_titles_display_without_any_new_work(self):
        items = [{"name": "삼성전자", "symbol": "005930"}]
        with patch.object(subject, "read_issue_headlines", return_value={
            subject._persisted_key("kr", items[0]): "자사주 소각 이슈",
        }), patch.object(subject, "read_news_metadata_for_stocks") as source:
            result = subject.get_market_issue_headlines("kr", items)
            self.assertEqual(result["items"][0]["headline"], "자사주 소각 이슈")
            self.assertEqual(result["items"][0]["status"], "ready")
            self.assertFalse(result["pending"])
            source.assert_not_called()

    def test_twenty_rows_use_one_batch_and_save_only_verified_results(self):
        items = [{"name": f"종목{i}", "symbol": f"{i:06d}"} for i in range(20)]
        source = {item["symbol"]: [{"title": f"{item['name']} 공급 계약 체결"}] for item in items}
        with patch.object(subject, "read_issue_headlines", return_value={}), \
             patch.object(subject, "read_news_metadata_for_stocks", return_value=source) as reader, \
             patch.object(subject, "_issue_from_metadata", side_effect=lambda name, articles: {
                 "headline": f"{name} 계약 이슈",
                 "tags": ["수주"],
                 "evidence_source": "news_title_description",
             }), \
             patch.object(subject, "save_issue_headlines", return_value=True) as writer:
            first = subject.get_market_issue_headlines("kr", items)
            self.assertEqual(len(first["items"]), 20)
            self._await_jobs()
            second = subject.get_market_issue_headlines("kr", items)
            self.assertFalse(second["pending"])
            self.assertEqual(len([x for x in second["items"] if x["status"] == "ready"]), 20)
            reader.assert_called_once()
            writer.assert_called_once()
            self.assertEqual(len(writer.call_args.args[1]), 20)

    def test_unverified_news_never_generates_fake_titles_or_db_writes(self):
        items = [{"name": "삼성전자", "symbol": "005930"}]
        with patch.object(subject, "read_issue_headlines", return_value={}), \
             patch.object(subject, "read_news_metadata_for_stocks", return_value={
                 "005930": [{"title": "다른 회사의 사업 계약"}],
             }), patch.object(subject, "save_issue_headlines") as writer:
            subject.get_market_issue_headlines("kr", items)
            self._await_jobs()
            result = subject.get_market_issue_headlines("kr", items)
            self.assertEqual(result["items"][0]["status"], "unavailable")
            self.assertEqual(result["items"][0]["headline"], "")
            writer.assert_not_called()

    def test_no_full_analysis_is_called_and_explicit_ownership_is_required(self):
        unrelated = [{"title": "다른 회사의 공급 계약 체결", "description": "기술 투자 확대"}]
        self.assertIsNone(subject._issue_from_metadata("삼성전자", unrelated))
        self.assertNotIn("get_shared_stock_news_result", subject.__dict__)

    def test_bad_symbol_and_oversized_list_rejected(self):
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines("kr", [{"name": "SK", "symbol": "NVDA"}])
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [{"name": "x", "symbol": "005930"}] * 21,
            )
