"""Mock-only tests for TradingView article-detail enrichment.

These tests use fake HTTP responses and never contact TradingView.
"""
import io
import json
import unittest
import urllib.error
import sys

# The gateway stages this test under /run/gaemi-gateway; add the existing
# application root so the test imports the installed backend package.
APP_ROOT = "/opt/gaemigtp-news/app"
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

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

        rows, stats = enrich_articles(
            [{"id": "one", "title": "Title"}],
            max_requests=0,
            api_key="test",
            opener=unexpected,
        )
        self.assertEqual(stats["requested"], 0)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(rows[0]["title"], "Title")

    def test_duplicate_article_is_requested_once(self):
        calls = []

        def fake(request, timeout):
            calls.append(request.full_url)
            return FakeResponse({
                "success": True,
                "data": {"summary": "A verified provider summary"},
            })

        rows, stats = enrich_articles(
            [
                {"id": "tag:abc/1", "title": "News"},
                {"id": "tag:abc/1", "title": "News duplicate"},
            ],
            max_requests=2,
            api_key="test",
            opener=fake,
        )
        self.assertEqual(stats["requested"], 1)
        self.assertEqual(stats["summarized"], 1)
        self.assertEqual(rows[0]["detail_summary"], "A verified provider summary")
        self.assertEqual(len(calls), 1)
        self.assertIn("tag%3Aabc%2F1", calls[0])

    def test_headline_permission_does_not_prevent_detail_lookup(self):
        calls = []

        def fake(request, timeout):
            calls.append(request.full_url)
            return FakeResponse({
                "success": True,
                "data": {
                    "body": "Detail API body",
                    "permission": "headline",
                },
            })

        rows, stats = enrich_articles(
            [{"id": "one", "permission": "headline"}],
            max_requests=2,
            api_key="test",
            opener=fake,
        )
        self.assertEqual(stats["blocked"], 1)
        self.assertEqual(stats["requested"], 1)
        self.assertEqual(stats["bodies"], 1)
        self.assertEqual(rows[0]["detail_body"], "Detail API body")
        self.assertEqual(len(calls), 1)

    def test_rate_limit_stops_remaining_requests(self):
        calls = []

        def fake(request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(
                request.full_url, 429, "limit", {}, io.BytesIO(b"")
            )

        rows, stats = enrich_articles(
            [{"id": "one"}, {"id": "two"}],
            max_requests=10,
            api_key="test",
            opener=fake,
        )
        self.assertEqual(stats["requested"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["halted_http_status"], 429)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("detail_body", rows[0])

    def test_body_is_not_mistaken_for_summary(self):
        def fake(request, timeout):
            return FakeResponse({
                "success": True,
                "data": {"body": "Copyrighted full text"},
            })

        rows, stats = enrich_articles(
            [{"id": "one"}],
            max_requests=1,
            api_key="test",
            opener=fake,
        )
        self.assertEqual(stats["summarized"], 0)
        self.assertEqual(rows[0]["detail_checked"], "content")
        self.assertEqual(stats["bodies"], 1)
        self.assertEqual(rows[0]["detail_body"], "Copyrighted full text")
        self.assertNotIn("detail_summary", rows[0])

    def test_request_budget_is_respected_above_ten_articles(self):
        calls = []

        def fake(request, timeout):
            calls.append(request.full_url)
            return FakeResponse({
                "success": True,
                "data": {
                    "body": "Full article",
                    "summary": "Provider summary",
                },
            })

        items = [{"id": "article-%02d" % i} for i in range(12)]
        rows, stats = enrich_articles(
            items,
            max_requests=len(items),
            api_key="test",
            opener=fake,
        )
        self.assertEqual(len(calls), 12)
        self.assertEqual(stats["requested"], 12)
        self.assertEqual(stats["bodies"], 12)
        self.assertEqual(stats["summarized"], 12)
        self.assertTrue(all(row["detail_body"] for row in rows))

    def test_body_and_summary_are_kept_separate(self):
        def fake(request, timeout):
            return FakeResponse({
                "success": True,
                "data": {
                    "article": {
                        "body": "Full detailed article text.",
                        "summary": "A short provider summary.",
                    }
                },
            })

        rows, stats = enrich_articles(
            [{"id": "one", "permission": "provider"}],
            max_requests=1,
            api_key="test",
            opener=fake,
        )
        self.assertEqual(rows[0]["detail_body"], "Full detailed article text.")
        self.assertEqual(rows[0]["detail_summary"], "A short provider summary.")
        self.assertEqual(stats["bodies"], 1)
        self.assertEqual(stats["summarized"], 1)


if __name__ == "__main__":
    unittest.main()
