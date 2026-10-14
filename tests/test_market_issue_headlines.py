"""Representative issue coverage for every stock in a market ranking result."""
import time
import unittest
from unittest.mock import patch

from backend.services import market_issue_headlines as subject


class MarketIssueHeadlineTests(unittest.TestCase):
    def setUp(self):
        with subject._ISSUE_LOCK:
            subject._ISSUE_CACHE.clear()
            subject._ISSUE_PENDING.clear()

    def test_all_rows_start_without_stock_click_and_resolve(self):
        items = [{"name": f"종목{i}", "symbol": f"{i:06d}"} for i in range(20)]
        with patch.object(subject, "get_shared_stock_news_result", side_effect=lambda name, **kw: {
            "issue_briefs": [{"headline": f"{name} 계약 이슈"}],
        }):
            response = subject.get_market_issue_headlines("kr", items)
            self.assertEqual(len(response["items"]), 20)
            for _ in range(200):
                with subject._ISSUE_LOCK:
                    pending = list(subject._ISSUE_PENDING.values())
                if not pending:
                    break
                for future in pending:
                    future.result(timeout=2)
            second = subject.get_market_issue_headlines("kr", items)
        self.assertFalse(second["pending"])
        self.assertEqual(len([item for item in second["items"] if item["status"] == "ready"]), 20)

    def test_missing_verified_body_does_not_create_fake_issue(self):
        items = [{"name": "삼성SDI", "symbol": "006400"}]
        with patch.object(subject, "get_shared_stock_news_result", return_value={"issue_briefs": []}):
            subject.get_market_issue_headlines("kr", items)
            with subject._ISSUE_LOCK:
                futures = list(subject._ISSUE_PENDING.values())
            for future in futures:
                future.result(timeout=2)
            result = subject.get_market_issue_headlines("kr", items)
        self.assertEqual(result["items"][0]["status"], "unavailable")
        self.assertEqual(result["items"][0]["headline"], "")

    def test_bad_symbol_and_oversized_list_rejected(self):
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines("kr", [{"name":"SK", "symbol":"NVDA"}])
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines("kr", [{"name":"x", "symbol":"005930"}] * 21)
