"""Mock-only tests: never send a real TradingView API request."""
import io
import json
import unittest
import urllib.error

from backend.providers.tradingview_news_detail import enrich_articles


class FakeResponse:
    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.data[:size]


class DetailTests(unittest.TestCase):
    def test_zero_budget_never_calls_api(self):
        def unexpected(*args, **kwargs):
            raise AssertionError("network called")
        rows, stat = enrich_articles([{"id": "one", "title": "Title"}], max_requests=0, api_key="test", opener=unexpected)
        self.assertEqual(stat["requested"], 0)
        self.assertEqual(rows[0]["title"], "Title")

    def test_one_detail_and_no_duplicate(self):
        calls = []
        def fake(request, timeout):
            calls.append(request.full_url)
            return FakeResponse({"success": True, "data": {"description": "A verified factual description"}})
        rows, stat = enrich_articles(
            [{"id": "tag:abc/1", "title": "News", "permission": "provider"},
             {"id": "tag:abc/1", "title": "News duplicate", "permission": "provider"}],
            max_requests=2, api_key="test", opener=fake,
        )
        self.assertEqual(stat["requested"], 1)
        self.assertEqual(stat["described"], 1)
        self.assertEqual(rows[0]["shortDescription"], "A verified factual description")
        self.assertEqual(len(calls), 1)
        self.assertIn("tag%3Aabc%2F1", calls[0])

    def test_headline_listing_still_checks_detail(self):
        calls = []
        def fake(request, timeout):
            calls.append(request.full_url)
            return FakeResponse({"success": True, "data": {"body": "Detail API body", "permission": "headline"}})
        rows, stat = enrich_articles([{"id": "one", "permission": "headline"}],
                                     max_requests=2, api_key="test", opener=fake)
        self.assertEqual(stat["blocked"], 1)
        self.assertEqual(stat["requested"], 1)
        self.assertEqual(stat["bodies"], 1)
        self.assertEqual(rows[0]["detail_body"], "Detail API body")
        self.assertEqual(len(calls), 1)

    def test_rate_limit_stops_other_requests(self):
        calls = []
        def fake(request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 429, "limit", {}, io.BytesIO(b""))
        rows, stat = enrich_articles([{"id": "one"}, {"id": "two"}],
                                     max_requests=10, api_key="test", opener=fake)
        self.assertEqual(stat["requested"], 1)
        self.assertEqual(stat["failed"], 1)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("shortDescription", rows[0])

    def test_body_is_not_mistaken_for_summary(self):
        def fake(request, timeout):
            return FakeResponse({"success": True, "data": {"body": "Copyrighted full text"}})
        rows, stat = enrich_articles([{"id": "one"}], max_requests=1,
                                     api_key="test", opener=fake)
        self.assertEqual(stat["described"], 0)
        self.assertEqual(rows[0]["detail_checked"], "content")
        self.assertEqual(stat["bodies"], 1)
        self.assertEqual(rows[0]["detail_body"], "Copyrighted full text")
        self.assertEqual(stat["summarized"], 0)

    def test_body_description_summary_are_separate(self):
        def fake(request, timeout):
            return FakeResponse({"success": True, "data": {"article": {
                "body": "Full detailed article text.",
                "description": "An article description.",
                "summary": "A short provider summary.",
            }}})
        rows, stat = enrich_articles([{"id": "one", "permission": "provider"}],
                                     max_requests=1, api_key="test", opener=fake)
        self.assertEqual(rows[0]["detail_body"], "Full detailed article text.")
        self.assertEqual(rows[0]["detail_description"], "An article description.")
        self.assertEqual(rows[0]["detail_summary"], "A short provider summary.")
        self.assertEqual(stat["bodies"], 1)
        self.assertEqual(stat["described"], 1)
        self.assertEqual(stat["summarized"], 1)


if __name__ == "__main__":
    unittest.main()
