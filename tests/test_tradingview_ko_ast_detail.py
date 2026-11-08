"""TradingView KO AST detail regressions; uses fake responses, no API calls."""
import io
import json
import unittest
import urllib.error

from backend.providers.tradingview_news_detail import enrich_articles


class FakeResponse:
    def __init__(self, payload):
        self.raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _size=-1):
        return self.raw


class KoreanAstBodyTests(unittest.TestCase):
    def test_korean_ast_text_is_body_not_description(self):
        urls = []

        def opener(request, timeout):
            urls.append(request.full_url)
            return FakeResponse({"success": True, "data": {
                "language": "ko",
                "permission": "headline",
                "shortDescription": "짧은 설명문",
                "astDescription": {
                    "type": "root",
                    "children": [
                        {"type": "p", "children": ["미국 고용지표가", " 예상보다 높았습니다."]},
                        {"type": "p", "children": ["기술주가 상승했고", " 국채금리도 움직였습니다."]},
                    ],
                },
            }})

        rows, stats = enrich_articles(
            [{"id": "tag:reuters.com,2026:newsml_ABC:0", "title": "미국 고용 호조",
              "permission": "headline"}],
            max_requests=1, opener=opener, api_key="fake",
        )
        self.assertEqual(len(urls), 1)
        self.assertIn("?lang=ko", urls[0])
        self.assertIn("tag%3Areuters.com", urls[0])
        self.assertEqual(stats["bodies"], 1)
        self.assertEqual(stats["blocked"], 1)
        self.assertEqual(stats["summarized"], 0)
        self.assertEqual(
            rows[0]["detail_body"],
            "미국 고용지표가 예상보다 높았습니다.\n\n기술주가 상승했고 국채금리도 움직였습니다.",
        )
        self.assertNotIn("shortDescription", rows[0])
        self.assertNotIn("detail_summary", rows[0])

    def test_rich_text_children_and_link_text_without_url(self):
        def opener(request, timeout):
            return FakeResponse({"success": True, "data": {
                "astDescription": {"type": "root", "children": [
                    {"type": "p", "children": [
                        "이슈는 ", {"type": "b", "children": ["반도체주"]},
                        "와 ", {"type": "url", "params": {
                            "url": "https://not-a-body.example/", "linkText": "연준 정책",
                        }}, "입니다.",
                    ]},
                ]},
            }})
        rows, stats = enrich_articles([{"id": "rich"}], max_requests=1,
                                     api_key="fake", opener=opener)
        self.assertEqual(stats["bodies"], 1)
        self.assertEqual(rows[0]["detail_body"], "이슈는 반도체주와 연준 정책입니다.")
        self.assertNotIn("https://", rows[0]["detail_body"])
        self.assertNotIn("root", rows[0]["detail_body"])

    def test_description_only_is_not_mistaken_for_body(self):
        def opener(request, timeout):
            return FakeResponse({"success": True, "data": {
                "shortDescription": "설명문은 오지만 본문은 비어 있습니다.",
                "astDescription": {"type": "root", "children": []},
            }})
        rows, stats = enrich_articles([{"id": "empty"}], max_requests=1,
                                     api_key="fake", opener=opener)
        self.assertEqual(stats["bodies"], 0)
        self.assertEqual(rows[0]["detail_checked"], "no_content")
        self.assertNotIn("detail_body", rows[0])

    def test_existing_plain_body_still_works(self):
        def opener(request, timeout):
            return FakeResponse({"success": True, "data": {
                "body": "이미 일반 본문이 있습니다.",
                "astDescription": {"type": "root", "children": ["다른 문자열"]},
                "summary": "별도의 요약",
            }})
        rows, stats = enrich_articles([{"id": "plain"}], max_requests=1,
                                     api_key="fake", opener=opener)
        self.assertEqual(rows[0]["detail_body"], "이미 일반 본문이 있습니다.")
        self.assertEqual(rows[0]["detail_summary"], "별도의 요약")
        self.assertEqual(stats["bodies"], 1)

    def test_duplicates_call_once(self):
        called = []
        def opener(request, timeout):
            called.append(request.full_url)
            return FakeResponse({"success": True, "data": {
                "astDescription": {"type": "root", "children": ["본문"]},
            }})
        rows, stats = enrich_articles([{"id": "one"}, {"id": "one"}],
                                     max_requests=3, api_key="fake", opener=opener)
        self.assertEqual(len(called), 1)
        self.assertEqual(stats["requested"], 1)
        self.assertEqual(stats["skipped"], 1)

    def test_budget_zero_cannot_call(self):
        def opener(request, timeout):
            raise AssertionError("unexpected network call")
        _, stats = enrich_articles([{"id": "one"}], max_requests=0,
                                  api_key="fake", opener=opener)
        self.assertEqual(stats["requested"], 0)

    def test_rate_limit_stops_following_detail_requests(self):
        called = []
        def opener(request, timeout):
            called.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 429, "limit", {}, io.BytesIO())
        _, stats = enrich_articles([{"id": "one"}, {"id": "two"}],
                                  max_requests=2, api_key="fake", opener=opener)
        self.assertEqual(len(called), 1)
        self.assertEqual(stats["requested"], 1)
        self.assertEqual(stats["failed"], 1)


if __name__ == "__main__":
    unittest.main()
