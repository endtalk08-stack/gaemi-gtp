"""Offline checks for AI issue adaptation to the existing snapshot shape."""
import importlib.util
import pathlib
import sys
import unittest

OPS = pathlib.Path(__file__).resolve().parents[1] / "ops"
sys.path.insert(0, str(OPS))
from staged_ai_issue_display_adapter import to_issue_briefs


class DisplayAdapterTests(unittest.TestCase):
    def test_zero_issues(self):
        self.assertEqual(to_issue_briefs([], "17:13", ["삼성전자"]), [])

    def test_two_issues_keep_ai_content(self):
        issues = [
            {"headline": "수요 증가", "summary": "수요 확대", "tags": ["#수요"]},
            {"headline": "투자 확대", "summary": "설비 투자", "tags": ["#투자"]},
        ]
        result = to_issue_briefs(issues, "17:13", ["삼성전자"])
        self.assertEqual([row["headline"] for row in result], ["수요 증가", "투자 확대"])
        self.assertEqual(result[0]["summary"], "수요 확대")
        self.assertEqual(result[0]["tags"], ["수요"])
        self.assertEqual(result[0]["time"], "")
        self.assertEqual(result[0]["stock_names"], ["삼성전자"])
        self.assertEqual(result[0]["reaction_at"], "")

    def test_four_issues_rejected(self):
        issues = [{"headline": "A", "summary": "B", "tags": []} for _ in range(4)]
        with self.assertRaises(ValueError):
            to_issue_briefs(issues, "", [])

    def test_invalid_stock_names_rejected(self):
        with self.assertRaises(ValueError):
            to_issue_briefs([], "", ["삼성전자", None])


if __name__ == "__main__":
    unittest.main()
