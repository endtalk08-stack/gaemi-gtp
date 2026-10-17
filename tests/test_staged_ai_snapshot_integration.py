"""Offline tests for keeping the original news payload intact."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops"))
from staged_ai_snapshot_integration import with_ai_issue_briefs


class SnapshotIntegrationTests(unittest.TestCase):
    def test_replaces_only_issue_briefs(self):
        original = {
            "issue_briefs": [{"headline": "기존 이슈"}],
            "paired_news_items": [{"title": "원문 뉴스", "published_at": "2026-10-17"}],
            "keyword_storyboard": [{"keyword": "HBM"}],
            "_news_status": {"ok": True},
        }
        issues = [{"headline": "AI 이슈", "summary": "AI 내용", "tags": ["#HBM"]}]
        updated = with_ai_issue_briefs(
            original, issues, display_time="17:13", stock_names=["삼성전자"]
        )
        self.assertEqual(updated["issue_briefs"][0]["headline"], "AI 이슈")
        self.assertEqual(updated["_ai_issue_briefs"], updated["issue_briefs"])
        self.assertEqual(updated["_code_issue_briefs"], original["issue_briefs"])
        for key in ("paired_news_items", "keyword_storyboard", "_news_status"):
            self.assertEqual(updated[key], original[key])
        self.assertEqual(original["issue_briefs"][0]["headline"], "기존 이슈")

    def test_zero_issues_retains_news(self):
        original = {"issue_briefs": [{"headline": "기존"}], "paired_news_items": [1]}
        updated = with_ai_issue_briefs(original, [], display_time="", stock_names=[])
        self.assertEqual(updated["issue_briefs"], original["issue_briefs"])
        self.assertEqual(updated["_ai_issue_briefs"], [])
        self.assertEqual(updated["paired_news_items"], [1])

    def test_invalid_payload_rejected(self):
        with self.assertRaises(ValueError):
            with_ai_issue_briefs([], [], display_time="", stock_names=[])


if __name__ == "__main__":
    unittest.main()
