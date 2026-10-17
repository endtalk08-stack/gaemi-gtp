"""Render sidebar reads existing DigitalOcean snapshots only."""
import unittest
from unittest.mock import patch

from backend.services import market_issue_headlines as subject


class MarketIssueHeadlineTests(unittest.TestCase):
    def test_existing_worker_brief_is_displayed_without_news_processing(self):
        items = [{"name": "삼성전자", "symbol": "005930"}]
        briefs = [{"headline": "AI 반도체 이슈", "summary": "확인된 뉴스",
                   "stock_names": ["삼성전자"], "tags": ["AI반도체"]}]
        with patch.object(subject, "_read_worker_briefs",
                          return_value={"삼성전자": briefs}) as reader:
            result = subject.get_market_issue_headlines("kr", items)
        self.assertEqual(result["items"][0]["status"], "ready")
        self.assertEqual(result["items"][0]["headline"], "AI 반도체 이슈")
        self.assertFalse(result["pending"])
        reader.assert_called_once_with("kr", ["삼성전자"])

    def test_missing_worker_brief_is_not_generated_or_saved(self):
        items = [{"name": "삼성SDI", "symbol": "006400"}]
        with patch.object(subject, "_read_worker_briefs", return_value={}) as reader:
            result = subject.get_market_issue_headlines("kr", items)
        self.assertEqual(result["items"][0]["status"], "unavailable")
        self.assertEqual(result["items"][0]["headline"], "")
        self.assertFalse(result["pending"])
        reader.assert_called_once()

    def test_twenty_rows_have_one_worker_snapshot_read(self):
        items = [{"name": f"종목{i}", "symbol": f"{i:06d}"} for i in range(20)]
        with patch.object(subject, "_read_worker_briefs", return_value={}) as reader:
            result = subject.get_market_issue_headlines("kr", items)
        self.assertEqual(len(result["items"]), 20)
        self.assertTrue(all(row["status"] == "unavailable" for row in result["items"]))
        reader.assert_called_once()

    def test_bad_symbol_and_oversized_list_rejected(self):
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines("kr", [{"name": "SK", "symbol": "NVDA"}])
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [{"name": "x", "symbol": "005930"}] * 21,
            )


if __name__ == "__main__":
    unittest.main()
