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
        self.assertGreater(shared[0]["analysis_event_strength"], 0)
        self.assertTrue(shared[0]["analysis_material_signal"])
        kr_keywords = build_connected_keyword_test(copy.deepcopy(shared), "테슬라", max_keywords=3)
        us_keywords = build_connected_keyword_test(
            copy.deepcopy(news_feed.select_stock_news_for_analysis(self.rows, "테슬라", 50)),
            "테슬라", max_keywords=3,
        )
        self.assertEqual(kr_keywords, us_keywords)
        self.assertEqual(len(kr_keywords["articles"]), 1)

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

    def test_us_without_eligible_kr_fallback_returns_existing_original_error(self):
        row = item(
            "테슬라, 배터리 공급 계약 확대",
            "테슬라는 새로운 공급 계약을 체결했다.",
            url="https://example.org/tesla-contract",
        )
        with patch.object(news_result, "read_selected_article_details",
                          return_value=[{"source": "fetch_failed", "text": ""}]):
            result = news_result.build_stock_news_result(
                "테슬라", market="미국", raw_news_list=[row],
            )
        # The existing shared pipeline reports a fetch failure if every
        # nominated original is unreadable; it must never substitute a
        # publisher description or invented issue for that missing body.
        self.assertEqual(result.get("_news_status"), "error")
        self.assertEqual(result.get("issue_briefs"), [])

    def test_us_and_kr_use_same_issue_text_builder_without_us_fallback(self):
        from backend.services.issue_briefs import build_issue_briefs, _article_excerpt
        from backend.services.verified_fact_headline import attach_verified_source_citations
        body = (
            "테슬라는 배터리 공급 계약을 체결했다. "
            "테슬라는 연간 공급 물량을 늘린다. "
            "계약 효력은 내년부터 발생한다. "
            "네 번째 문장은 표시되면 안 된다."
        )
        row = {
            "title": "테슬라, 배터리 공급 계약 체결",
            "published_at": NOW.isoformat(),
            "url": "https://example.org/tesla-contract",
            "storyboard_keyword": "공급계약",
            "storyboard_time": "10:00",
            "grounded_tags": ["공급계약"],
            "article_keywords": ["공급계약"],
            "storyboard_keywords": ["공급계약"],
            "themes": ["공급계약"],
        }
        expected = build_issue_briefs([row], "테슬라", body_texts=[body], market="국내")
        actual = build_issue_briefs([row], "테슬라", body_texts=[body], market="미국")
        self.assertEqual(actual, expected)
        cited = attach_verified_source_citations(actual, [row], [body], "테슬라")
        self.assertEqual(cited[0]["summary"], _article_excerpt(body))
        self.assertEqual(cited[0]["headline"], expected[0]["headline"])
        self.assertEqual(cited[0]["tags"], expected[0]["tags"])
        self.assertEqual(cited[0]["source_articles"][0]["url"], row["url"])
        self.assertNotIn("네 번째 문장", cited[0]["summary"])

    def test_us_and_kr_same_company_fallback_when_original_not_readable(self):
        # Real fallback eligibility and priority are shared, not an added US
        # title/description extractor. The URL/date remain the same source.
        article = item(
            "테슬라 신용등급 상향 발표",
            "테슬라는 신용등급 상향을 발표했다.",
            url="https://example.org/tesla-credit-upgrade",
        )
        options = {
            "title": article["title"],
            "description": article["description"],
            "published_at": article["published_at"],
            "url": article["url"],
            "relation_type": "direct",
            "event_owner": "테슬라",
            "storyboard_time": "10:00",
        }
        def run(market):
            with patch.object(news_result, "build_simple_today_news", return_value=[options]), \
                 patch.object(news_result, "select_keyword_storyboard_news", return_value=[]), \
                 patch.object(news_result, "read_selected_article_details", return_value=[]):
                return news_result.build_stock_news_result(
                    "테슬라", market=market, raw_news_list=[article],
                )
        domestic = run("국내")
        america = run("미국")
        self.assertEqual(domestic["_news_status"], "ok")
        self.assertEqual(america["_news_status"], "ok")
        self.assertEqual(len(domestic["issue_briefs"]), 1)
        self.assertEqual(len(america["issue_briefs"]), 1)
        kr_brief, us_brief = domestic["issue_briefs"][0], america["issue_briefs"][0]
        for key in ("headline", "summary", "tags", "stock_names", "time",
                    "reaction_at", "evidence_source", "material_direction"):
            self.assertEqual(us_brief.get(key), kr_brief.get(key), key)
        self.assertEqual(us_brief["evidence_source"], "news_title_description")
        self.assertEqual(us_brief["summary"], article["description"])
        self.assertEqual(us_brief["source_articles"][0]["url"], article["url"])
        self.assertEqual(us_brief["source_articles"][0]["published_at"], article["published_at"])
        self.assertNotIn("source_articles", kr_brief)


if __name__ == "__main__":
    unittest.main()
