"""Offline validation checks for staged Groq issue selection."""
import importlib.util
import json
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "ops" / "staged_daily_groq_issues.py"
spec = importlib.util.spec_from_file_location("staged_daily_groq_issues", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GroqIssueTests(unittest.TestCase):
    def test_empty_issues(self):
        self.assertEqual(module.parse_issues('{"issues":[]}'), [])

    def test_three_issues(self):
        item = {"headline": "기사 제목", "summary": "쉬운 내용", "tags": ["#주식"]}
        self.assertEqual(len(module.parse_issues(json.dumps({"issues": [item] * 3}))), 3)

    def test_reject_four(self):
        item = {"headline": "제목", "summary": "내용", "tags": []}
        with self.assertRaises(ValueError):
            module.parse_issues(json.dumps({"issues": [item] * 4}))

    def test_reject_wrong_fields(self):
        with self.assertRaises(ValueError):
            module.parse_issues('{"issues":[{"title":"x","summary":"y","tags":[]}]}')

    def test_reject_bad_tags(self):
        with self.assertRaises(ValueError):
            module.parse_issues('{"issues":[{"headline":"x","summary":"y","tags":["x"]}]}')

    def test_no_news_does_not_call_api(self):
        self.assertEqual(module.analyze_news("NVDA", []), [])


if __name__ == "__main__":
    unittest.main()
