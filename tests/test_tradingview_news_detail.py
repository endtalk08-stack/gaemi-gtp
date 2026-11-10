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



class BodyHighlightsTests(unittest.TestCase):
    def test_summary_uses_original_article_sentences_only(self):
        from backend.services.tradingview_news_page import extract_body_highlights
        body = (
            "엔비디아는 데이터센터용 차세대 칩을 공개했다. "
            "시장에서는 엔비디아 매출이 30% 증가할 것으로 예상한다. "
            "이번 신제품에는 효율성을 높이는 기술이 적용됐다."
            "\n\n법적 고지: 결과는 달라질 수 있다."
        )
        result = extract_body_highlights(body, "엔비디아 매출 30% 증가")
        self.assertIn("엔비디아", result)
        self.assertIn("30%", result)
        self.assertNotIn("법적 고지", result)
        self.assertLessEqual(len(result), 420)
        self.assertEqual(extract_body_highlights(""), "")

    def test_r2_list_excerpt_is_based_on_body_not_description(self):
        from backend.services.tradingview_news_page import normalize_article
        row = normalize_article({
            "id": "sample-1",
            "title": "엔비디아 데이터센터 제품 발표",
            "news_categories": ["overall"],
            "detail_body": "엔비디아가 데이터센터용 신제품을 발표했다. 출하 시기는 내년으로 예정돼 있다.",
            "detail_publication_allowed": True,
            "detail_rights_confirmed": True,
        })
        self.assertTrue(row["body_available"])
        self.assertIn("엔비디아", row["list_excerpt"])
        self.assertEqual(row["summary"], "")
        self.assertEqual(row["description"], "")

    def test_no_publication_rights_does_not_expose_private_body(self):
        from backend.services.tradingview_news_page import normalize_article
        row = normalize_article({
            "id": "sample-2",
            "title": "엔비디아 데이터센터 제품 발표",
            "news_categories": ["overall"],
            "detail_body": "엔비디아가 데이터센터용 신제품을 발표했다.",
        })
        self.assertEqual(row["body"], "")
        self.assertEqual(row["list_excerpt"], "")



class SelectedNewsTests(unittest.TestCase):
    def test_only_classified_news_reaches_detail_queue(self):
        from backend.services.tradingview_news_page import select_articles
        items = [
            {"id": "stock-1", "title": "엔비디아 실적 발표",
             "news_categories": ["overall"],
             "relatedSymbols": [{"symbol": "NASDAQ:NVDA"}]},
            {"id": "market-1", "title": "미국 소비자물가지수 CPI 발표",
             "news_categories": ["overall"]},
            {"id": "ignored-1", "title": "홍보 행사에 참석한 연예인",
             "news_categories": ["overall"]},
        ]
        self.assertEqual([x["id"] for x in select_articles(items)],
                         ["stock-1", "market-1"])

    def test_identical_headlines_keep_an_existing_body_without_requery(self):
        from backend.services.tradingview_news_page import select_articles, build_snapshot
        items = [
            {"id": "new-id", "title": "엔비디아 실적 발표", "news_categories": ["overall"],
             "relatedSymbols": [{"symbol": "NASDAQ:NVDA"}]},
            {"id": "old-id", "title": "엔비디아 실적 발표", "news_categories": ["overall"],
             "relatedSymbols": [{"symbol": "NASDAQ:NVDA"}],
             "detail_body": "엔비디아는 실적이 크게 늘었다고 발표했다.",
             "detail_publication_allowed": True, "detail_rights_confirmed": True},
        ]
        selected = select_articles(items)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["id"], "old-id")
        self.assertEqual(build_snapshot(items)["count"], 1)

    def test_selected_detail_calls_only_selected_ids_with_mock_api(self):
        from backend.services.tradingview_news_page import select_articles
        from backend.providers.tradingview_news_detail import enrich_articles
        calls = []
        def fake(req, timeout):
            calls.append(req.full_url)
            return FakeResponse({"success": True, "data": {
                "astDescription": {"type": "p", "children": ["실적 발표 본문입니다."]}}})
        items = [
            {"id": "selected-1", "title": "엔비디아 실적 발표",
             "news_categories": ["overall"],
             "relatedSymbols": [{"symbol": "NASDAQ:NVDA"}]},
            {"id": "selected-1", "title": "엔비디아 실적 발표",
             "news_categories": ["overall"],
             "relatedSymbols": [{"symbol": "NASDAQ:NVDA"}]},
            {"id": "ignored-1", "title": "홍보 행사 안내",
             "news_categories": ["overall"]},
        ]
        rows, stats = enrich_articles(select_articles(items), max_requests=5,
                                     api_key="fake", opener=fake)
        self.assertEqual(stats["requested"], 1)
        self.assertEqual(len(calls), 1)
        self.assertIn("selected-1", calls[0])
        self.assertEqual(rows[0]["detail_body"], "실적 발표 본문입니다.")




class TwiceDailyActivationTests(unittest.TestCase):
    def test_default_budget_is_limited_and_explicit_zero_stops_calls(self):
        from unittest import mock
        from backend.tradingview_news_worker import _bounded_detail_budget
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(_bounded_detail_budget(), 20)
        with mock.patch.dict("os.environ", {"NEWS_DETAIL_REQUEST_BUDGET": "0"}):
            self.assertEqual(_bounded_detail_budget(), 0)
        with mock.patch.dict("os.environ", {"NEWS_DETAIL_REQUEST_BUDGET": "1000"}):
            self.assertEqual(_bounded_detail_budget(), 20)

    def test_outside_collection_windows_never_invokes_detail_api(self):
        from unittest import mock
        from backend import tradingview_news_worker as worker
        with mock.patch.object(worker.tradingview_news_bundle, "_basic_slot", return_value=(None, None)):
            with mock.patch.object(worker, "enrich_articles", side_effect=AssertionError("API must not be called")):
                self.assertEqual(worker.enrich_cached_articles([{"id": "one"}]), [{"id": "one"}])

    def test_successful_slot_only_calls_detail_once_and_keeps_cache_selection(self):
        from unittest import mock
        from pathlib import Path
        from backend import tradingview_news_worker as worker
        import tempfile
        import json
        state = {
            "feed_version": worker.tradingview_news_bundle.FEED_VERSION,
            "last_slot": "20261110:premarket",
            "ok_categories": ["overall"],
            "failed_categories": [],
            "items": [
                {"id": "one", "title": "엔비디아 실적 발표", "news_categories": ["overall"],
                 "relatedSymbols": [{"symbol": "NASDAQ:NVDA"}]},
                {"id": "ignored", "title": "가을 축제 안내", "news_categories": ["overall"]},
            ],
        }
        with tempfile.TemporaryDirectory() as root:
            cache = Path(root) / "cache.json"
            cache.write_text(json.dumps(state), encoding="utf-8")
            def persist(updated):
                cache.write_text(json.dumps(updated), encoding="utf-8")
            def fake_enrich(rows, *, max_requests):
                self.assertEqual([r["id"] for r in rows], ["one"])
                self.assertEqual(max_requests, 20)
                return rows, {"requested": 1, "bodies": 0, "summarized": 0,
                              "blocked": 0, "failed": 0, "skipped": 0, "halted_http_status": None}
            with mock.patch.object(worker.tradingview_news_bundle, "_basic_slot",
                                   return_value=("premarket", "20261110:premarket")), \\
                 mock.patch.object(worker.tradingview_news_bundle, "CACHE_PATH", cache), \\
                 mock.patch.object(worker.tradingview_news_bundle, "_write", side_effect=persist), \\
                 mock.patch.object(worker, "enrich_articles", side_effect=fake_enrich) as mocked:
                first = worker.enrich_cached_articles(state["items"])
                self.assertEqual([r["id"] for r in first], ["one"])
                self.assertEqual(json.loads(cache.read_text())["detail_last_slot"], "20261110:premarket")
                self.assertEqual(json.loads(cache.read_text())["detail_daily_requests"], 1)
                worker.enrich_cached_articles(first)
                self.assertEqual(mocked.call_count, 1)

    def test_failed_list_collection_does_not_call_detail_api(self):
        from unittest import mock
        from pathlib import Path
        from backend import tradingview_news_worker as worker
        import tempfile, json
        with tempfile.TemporaryDirectory() as root:
            cache = Path(root) / "cache.json"
            cache.write_text(json.dumps({
                "feed_version": worker.tradingview_news_bundle.FEED_VERSION,
                "last_slot": "20261110:premarket",
                "ok_categories": [],
                "failed_categories": ["overall"],
                "items": [{"id":"one", "title":"엔비디아 실적 발표",
                           "news_categories":["overall"],
                           "relatedSymbols":[{"symbol":"NASDAQ:NVDA"}]}],
            }), encoding="utf-8")
            with mock.patch.object(worker.tradingview_news_bundle, "_basic_slot",
                                   return_value=("premarket", "20261110:premarket")), \\
                 mock.patch.object(worker.tradingview_news_bundle, "CACHE_PATH", cache), \\
                 mock.patch.object(worker, "enrich_articles", side_effect=AssertionError("API call")):
                self.assertEqual(len(worker.enrich_cached_articles([{"id": "one"}])), 1)


if __name__ == "__main__":
    unittest.main()
