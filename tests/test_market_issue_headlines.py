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

    def test_one_bad_ranked_symbol_does_not_blank_other_nineteen(self):
        items = [{"name": f"종목{i}", "symbol": f"{i:06d}"} for i in range(20)]
        items[7] = {"name": "형식오류", "symbol": "INVALID.SYMBOL"}
        briefs = [{"headline": "공급 계약 이슈", "summary": "확인된 뉴스"}]
        with patch.object(subject, "_read_worker_briefs",
                          return_value={"종목0": briefs, "종목19": briefs}) as reader:
            result = subject.get_market_issue_headlines("kr", items, skip_invalid=True)
        self.assertEqual(len(result["items"]), 20)
        self.assertEqual(result["items"][0]["headline"], "공급 계약 이슈")
        self.assertEqual(result["items"][7]["headline"], "")
        self.assertEqual(result["items"][7]["status"], "invalid")
        self.assertEqual(result["items"][19]["headline"], "공급 계약 이슈")
        self.assertEqual(result["items"][19]["symbol"], "000019")
        names = reader.call_args.args[1]
        self.assertEqual(len(names), 19)
        self.assertNotIn("형식오류", names)

    def test_invalid_ranked_row_retains_position_and_never_reads_fake_identity(self):
        items = [
            {"name": "삼성전자", "symbol": "005930"},
            {"name": "", "symbol": None},
            {"name": "삼성SDI", "symbol": "006400"},
        ]
        briefs = [{"headline": "반도체 계약 이슈"}]
        with patch.object(subject, "_read_worker_briefs",
                          return_value={"삼성전자": briefs}) as reader:
            rows = subject.get_market_issue_headlines("kr", items, skip_invalid=True)["items"]
        self.assertEqual([row["status"] for row in rows], ["ready", "invalid", "unavailable"])
        self.assertEqual([row["headline"] for row in rows], ["반도체 계약 이슈", "", ""])
        reader.assert_called_once_with("kr", ["삼성전자", "삼성SDI"])

    def test_all_invalid_rank_rows_do_not_query_db(self):
        with patch.object(subject, "_read_worker_briefs") as reader:
            result = subject.get_market_issue_headlines(
                "kr", [{"name": "없는 종목", "symbol": "bad"}], skip_invalid=True,
            )
        reader.assert_not_called()
        self.assertEqual(result["items"][0]["headline"], "")

    def test_strict_external_requests_remain_strict(self):
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [
                    {"name": "삼성전자", "symbol": "005930"},
                    {"name": "형식오류", "symbol": "INVALID.SYMBOL"},
                ],
            )
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [], skip_invalid=True,
            )
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [{"name": "정상", "symbol": "005930"}] * 21,
                skip_invalid=True,
            )

    def test_bad_symbol_and_oversized_list_rejected(self):
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines("kr", [{"name": "SK", "symbol": "NVDA"}])
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [{"name": "x", "symbol": "005930"}] * 21,
            )


if __name__ == "__main__":
    unittest.main()
