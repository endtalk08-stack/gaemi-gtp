"""Offline regression tests for staged AI failure and source-link safety."""
import importlib.util
import json
import pathlib
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("staged_daily_groq_issues", ROOT / "ops/staged_daily_groq_issues.py")
groq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(groq)


class StagedSafetyTests(unittest.TestCase):
    def test_zero_issues_is_valid_not_an_error(self):
        self.assertEqual(groq.parse_issues('{"issues":[]}'), [])

    def test_bad_response_never_becomes_a_valid_empty_result(self):
        for payload in ('', '{}', '{"issues":null}', '{"issues":{}}', '{"issues":[{}]}'):
            with self.subTest(payload=payload), self.assertRaises((ValueError, json.JSONDecodeError)):
                groq.parse_issues(payload)

    def test_failed_api_call_does_not_return_empty_success(self):
        import urllib.error
        with patch.dict("os.environ", {"GROQ_API_KEY": "offline-test"}), patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("mock-failure")
        ):
            with self.assertRaises(urllib.error.URLError):
                groq.analyze_news("NVDA", [{"title": "News", "body": "Verified body"}])

    def test_no_usable_articles_makes_no_request(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": "offline-test"}), patch(
            "urllib.request.urlopen"
        ) as call:
            self.assertEqual(groq.analyze_news("NVDA", [{"title": "Title only"}]), [])
            call.assert_not_called()

    def test_issue_response_has_no_source_article_identifiers(self):
        issue = {"headline": "Test", "summary": "Test summary", "tags": ["#AI"]}
        self.assertEqual(groq.parse_issues(json.dumps({"issues": [issue]})), [issue])
        self.assertNotIn("article_id", issue)
        self.assertNotIn("canonical_url", issue)

    def test_source_links_must_not_be_invented_from_ai_text(self):
        response = '{"issues":[{"headline":"Test","summary":"Text","tags":[]}]}'
        self.assertEqual(groq.parse_issues(response)[0]["headline"], "Test")
        self.assertNotIn("url", groq.parse_issues(response)[0])


if __name__ == "__main__":
    unittest.main()
