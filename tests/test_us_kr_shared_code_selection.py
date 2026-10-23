"""The same KR article, event, and keyword gates select US CODE inputs only.

Collector raw articles and paused AI input must never be changed.
"""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend.analysis.news import build_connected_keyword_test
from backend.services import news_feed, news_result


NOW = datetime.now(timezone.utc)


def item(title, desc, *, url, age_hours=1, **extra):
    return {
        "title": title, "description": desc, "url": url,
        "published_at": (NOW - timedelta(hours=age_hours)).isoformat(),
        **extra,
    }


class SharedDomesticUsSelectionTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            item("테슬라, 배터리 공급 계약 확대", "테슬라가 새로운 공급 계약을 체결했다.",
                 url="https://example.org/tesla-contract"),
            item("테슬라, 배터리 공급 계약 확대", "같은 기사의 중복 수집 결과",
                 url="https://example.org/tesla-contract"),
            item("애플 신제품 출시", "애플이 새로운 제품을 출시했다.",
                 url="https://example.org/apple"),
            item("미국 증시 오늘의 증시 브리핑", "테슬라 주가를 포함한 시장 동향",
                 url="https://example.org/roundup"),
            item("테슬라 설비투자 축소 발표", "테슬라는 내년 시설 투자 규모를 줄였다.",
                 url="https://example.org/old", age_hours=24 * 12),
        ]

    def test_us_code_gets_exact_same_kr_source_keywords_and_order(self):
        # The same helper is now used by the unchanged domestic feed.
        shared = news_feed.select_stock_news_for_analysis(self.rows, "테슬라", 50)
        self.assertEqual([x["url"] for x in shared], ["https://example.org/tesla-contract"])
        self.assertEqual(len(shared[0]["analysis_event_strength"] > 0 and [1]), 1)
        self.assertTrue(shared[0]["analysis_material_signal"])
        self.assertEqual(
            build_connected_keyword_test(copy.deepcopy(shared), "테슬라", max_keywords=3),
            build_connected_keyword_test(copy.deepcopy(shared), "테슬라", max_keywords=3),
        )

    def test_domestic_upstream_runs_shared_code_unchanged(self):
        rows = [
            item("삼성전자 대규모 계약 발표", "삼성전자가 새로운 공급 계약을 맺었다.",
                 url="https://example.org/samsung"),
            item("테슬라, 배터리 공급 계약 확대", "미국 회사 뉴스",
                 url="https://example.org/tesla"),
        ]
        with patch.object(news_feed, "_fetch_queries", return_value=rows), \
             patch.object(news_feed.official_company_news, "fetch_company_news", return_value=[]), \
             patch.object(news_feed.sec_filings, "fetch_recent_filings", return_value=[]):
            fetched = news_feed.fetch_stock_news("삼성전자", market="국내", limit=50)
        compared = news_feed.select_stock_news_for_analysis(rows, "삼성전자", 50)
        self.assertEqual(fetched, compared)
        self.assertEqual([x["url"] for x in fetched], ["https://example.org/samsung"])

    def test_us_fetch_keeps_unfiltered_raw_for_ai(self):
        raw = copy.deepcopy(self.rows)
        with patch.object(news_feed, "_fetch_queries", return_value=raw), \
             patch.object(news_feed.official_company_news, "fetch_company_news", return_value=[]), \
             patch.object(news_feed.sec_filings, "fetch_recent_filings", return_value=[]):
            fetched = news_feed.fetch_stock_news("테슬라", market="미국", limit=50)
        # Raw US feed retains duplicates, old news and other matched search
        # results for the existing separate AI branch.
        self.assertEqual(len(fetched), 5)
        self.assertEqual(len({x["url"] for x in fetched}), 4)
        self.assertEqual([x["url"] for x in news_feed.select_stock_news_for_analysis(
            fetched, "테슬라", 50)], ["https://example.org/tesla-contract"])
        self.assertEqual(raw, self.rows)

    def test_stock_result_calls_kr_selector_only_for_us_code_before_keywords(self):
        original = copy.deepcopy(self.rows)
        observed = {}
        def check_input(articles, stock_name):
            observed["articles"] = copy.deepcopy(articles)
            observed["name"] = stock_name
            raise RuntimeError("stop_after_first_stage")
        with patch.object(news_result, "score_stock_news", side_effect=check_input), \
             patch.object(news_result, "fetch_stock_news", side_effect=AssertionError("no refetch")), \
             patch.object(news_result, "build_connected_keyword_test", side_effect=AssertionError("later stage")):
            result = news_result.build_stock_news_result(
                "테슬라", market="미국", raw_news_list=original)
        self.assertEqual(result["_news_status"], "error")
        self.assertEqual(observed["name"], "테슬라")
        self.assertEqual([x["url"] for x in observed["articles"]],
                         ["https://example.org/tesla-contract"])
        self.assertEqual(original, self.rows)
        self.assertEqual(len(original), 5)


if __name__ == "__main__":
    unittest.main()
