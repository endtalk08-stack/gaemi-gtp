"""Market-wide US close brief: grounded quotes, news facts and cache."""
import datetime
import unittest
from unittest.mock import patch

from backend.services import us_market_close_brief as brief


_NOW = datetime.datetime(2026, 10, 14, 7, tzinfo=datetime.timezone.utc)
_SESSION = datetime.date(2026, 10, 13)
_MAIN = (
    "반도체 업종은 데이터센터 투자 확대 발표에 힘입어 강세를 보였다. "
    "전기차 업종은 수요 둔화 우려로 하락세를 기록했다. "
    "미국 국채금리는 발표된 지표의 영향으로 소폭 내려갔다. "
    "연준은 이번 주 물가 지표를 주시하고 있다고 밝혔다."
)


class USMarketCloseBriefTests(unittest.TestCase):
    def setUp(self):
        brief._CACHE = None
        brief._CACHED_AT = 0

    def tearDown(self):
        brief._CACHE = None
        brief._CACHED_AT = 0

    def test_quotes_require_exact_session_and_previous_close(self):
        rows = [
            {"date": "2026-10-12", "close": 100.0},
            {"date": "2026-10-13", "close": 106.0},
        ]
        with patch.object(brief, "fetch_daily_price_history", return_value=rows):
            self.assertEqual(brief._dated_index("^IXIC", _SESSION)["change_pct"], 6.0)
            self.assertIsNone(brief._dated_index("^IXIC", datetime.date(2026, 10, 14)))
        with patch.object(brief, "fetch_daily_price_history", return_value=[{"close": 106.0}]):
            self.assertIsNone(brief._dated_index("^IXIC", _SESSION))
        repeated_session = rows + [{"date": "2026-10-13", "close": 108.0}]
        with patch.object(brief, "fetch_daily_price_history", return_value=repeated_session):
            self.assertEqual(brief._dated_index("^IXIC", _SESSION)["change_pct"], 8.0)

    def test_news_categories_use_only_original_sentences(self):
        stories = [{"article_body": _MAIN, "source": "신문", "url": "https://example.com/us"}]
        categories = brief._fact_sections(stories)
        self.assertEqual(len(categories["주도업종"]), 1)
        self.assertIn("반도체", categories["주도업종"][0]["text"])
        self.assertEqual(len(categories["하락업종"]), 1)
        self.assertEqual(len(categories["원자재 · 금리 · 환율"]), 1)
        self.assertEqual(len(categories["경제지표 · 통화정책"]), 1)
        self.assertEqual(categories["거래대금 · 시장 강도"], [])

    def test_natural_korean_endings_keep_news_facts_and_uncertainty(self):
        self.assertEqual(
            brief._naturalize_fact("반도체 업종은 강세를 보였다."),
            "반도체 업종은 강세를 보였어.",
        )
        self.assertEqual(
            brief._naturalize_fact("매출은 증가할 것으로 전망된다."),
            "매출은 증가할 것으로 전망돼.",
        )
        self.assertEqual(
            brief._naturalize_fact("미국 4대 은행주가 하락했다."),
            "미국 4대 은행주가 하락했어.",
        )
        same_article = [
            {"text": "금융주가 하락했다.", "url": "https://example.com/a"},
            {"text": "메모리 반도체주도 약세를 보였다.", "url": "https://example.com/a"},
        ]
        self.assertEqual(
            brief._render_market_facts(same_article),
            "금융주가 하락했고, 메모리 반도체주도 약세를 보였어.",
        )
        other_article = [same_article[0], {**same_article[1], "url": "https://example.com/b"}]
        self.assertEqual(
            brief._render_market_facts(other_article),
            "금융주가 하락했어.\n\n메모리 반도체주도 약세를 보였어.",
        )

    def test_result_keeps_indices_and_shows_original_naver_title_summary(self):
        quotes = [
            {"name": "나스닥", "date": "2026-10-13", "change_pct": -1.22},
            {"name": "S&P500", "date": "2026-10-13", "change_pct": -0.3},
            {"name": "다우", "date": "2026-10-13", "change_pct": 0.15},
        ]
        article = {
            "title": "뉴욕증시, 나스닥 하락 마감",
            "description": "금리 우려가 지속되며 미국 증시가 약세로 마감했다.",
            "source": "신문", "url": "https://example.com/us",
            "market": "us", "news_scope": "market_close",
            "session_date": "2026-10-13",
            "detail_source": "naver_news_metadata",
            "published_at": "2026-10-14T00:30:00+00:00",
        }
        with patch.object(brief, "_index_changes", return_value=quotes) as prices, patch.object(
            brief, "build_us_market_close_news_result", return_value={"ok": True, "items": [article]}
        ) as news:
            first = brief.build_us_market_close_brief(now=_NOW)
            again = brief.build_us_market_close_brief(now=_NOW)

        self.assertTrue(first["ok"])
        indexed = next(x for x in first["sections"] if x["title"] == "주요 지수")
        self.assertIn("나스닥  -1.22%", indexed["content"])
        entry = next(x for x in first["sections"] if x["title"] == article["title"])
        self.assertEqual(entry["content"], article["description"])
        self.assertEqual(entry["article_url"], article["url"])
        self.assertEqual(entry["source_name"], "신문")
        self.assertNotIn("하락업종", [x["title"] for x in first["sections"]])
        self.assertEqual(first, again)
        prices.assert_called_once_with(_SESSION)
        news.assert_called_once_with(limit=4, now=_NOW, include_body=True)

    def test_market_article_gate_accepts_metadata_but_rejects_wrong_session(self):
        article = {
            "market": "us", "news_scope": "market_close",
            "session_date": "2026-10-13",
            "detail_source": "naver_news_metadata",
            "published_at": "2026-10-14T00:30:00+00:00",
            "title": "뉴욕증시 마감", "description": "뉴욕증시 하락 마감",
            "url": "https://example.com/us-close",
        }
        candidates = [
            article,
            {**article, "url": "https://example.com/wrong-session", "session_date": "2026-10-12"},
            {**article, "url": "https://example.com/no-body", "title": "미국 증시, 하락 마감"},
            {**article, "url": "https://example.com/foreign", "market": "kr"},
            {**article, "url": "https://example.com/preclose", "title": "뉴욕증시 장중"},
            {**article, "url": "https://example.com/future", "published_at": "2026-10-15T00:30:00+00:00"},
            {**article, "url": "javascript:alert(1)"},
            dict(article),
        ]
        accepted = brief._verified_session_articles(candidates, _SESSION, _NOW)
        self.assertEqual(accepted, [article, candidates[2]])

    def test_completed_session_reuses_memory_without_database_after_ttl(self):
        indices = [
            {"name": name, "date": "2026-10-13", "change_pct": -0.15}
            for name in ("나스닥", "S&P500", "다우")
        ]
        verified = {
            "title": "뉴욕증시 마감", "description": "다우 나스닥 마감",
            "market": "us", "news_scope": "market_close",
            "session_date": "2026-10-13", "detail_source": "jsonld_article_body",
            "published_at": "2026-10-14T00:30:00+00:00",
            "url": "https://example.com/us", "article_body": _MAIN,
        }
        with patch.object(brief, "_index_changes", return_value=indices) as prices, patch.object(
            brief, "build_us_market_close_news_result",
            return_value={"ok": True, "items": [verified]},
        ) as news, patch.object(brief.time, "monotonic", return_value=100) as clock:
            first = brief.build_us_market_close_brief(now=_NOW)
            clock.return_value = 100 + 60 * 60 * 12
            again = brief.build_us_market_close_brief(now=_NOW)

        self.assertEqual(first, again)
        prices.assert_called_once()
        news.assert_called_once()

    def test_incomplete_session_retries_after_short_cache_ttl(self):
        with patch.object(brief, "_index_changes", return_value=[]) as prices, patch.object(
            brief, "build_us_market_close_news_result",
            return_value={"ok": True, "items": []},
        ) as news, patch.object(brief.time, "monotonic", return_value=100) as clock:
            brief.build_us_market_close_brief(now=_NOW)
            clock.return_value = 100 + 601
            brief.build_us_market_close_brief(now=_NOW)

        self.assertEqual(prices.call_count, 2)
        self.assertEqual(news.call_count, 2)

    def test_missing_sources_return_explicit_absence_not_fabricated_data(self):
        with patch.object(brief, "_index_changes", return_value=[]), patch.object(
            brief, "build_us_market_close_news_result", return_value={"ok": True, "items": []}
        ):
            result = brief.build_us_market_close_brief(now=_NOW)
        self.assertFalse(result["ok"])
        self.assertEqual(result["indices"], [])
        self.assertFalse(any(x["title"] == "주요 지수" for x in result["sections"]))
        self.assertTrue(any(x["title"] == "마감시황 기사" for x in result["sections"]))


if __name__ == "__main__":
    unittest.main()
