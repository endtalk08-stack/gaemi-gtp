"""US market-close news reuses Naver titles/descriptions without body downloads."""
import datetime
import unittest
from unittest.mock import patch

from backend.services import us_market_close_news as subject

_NOW = datetime.datetime(2026, 10, 14, 7, tzinfo=datetime.timezone.utc)

def _item(title, when, url, description="뉴욕증시 주요 지수는 장을 마쳤다."):
    return {"title": title, "published_at": when, "url": url,
            "description": description, "source": "테스트 언론사"}

class USMarketCloseNewsTests(unittest.TestCase):
    def setUp(self):
        subject._CACHE = None
        subject._CACHED_AT = 0

    def tearDown(self):
        subject._CACHE = None
        subject._CACHED_AT = 0

    def test_previous_new_york_session_before_next_close(self):
        self.assertEqual(subject._last_completed_session(_NOW).isoformat(), "2026-10-13")
        self.assertEqual(
            subject._last_completed_session(
                datetime.datetime(2026, 10, 18, 15, tzinfo=datetime.timezone.utc)
            ).isoformat(), "2026-10-16"
        )

    def test_spaced_ny_market_headline_is_accepted_after_close(self):
        item = _item(
            "뉴욕 증시, 기술주 하락 마감",
            "2026-10-14T00:30:00+00:00",
            "https://example.com/ny-close",
        )
        self.assertTrue(subject._matches_market_close(
            item, datetime.date(2026, 10, 13), _NOW
        ))
        self.assertFalse(subject._matches_market_close(
            {**item, "title": "뉴욕 증시 장중 약세"},
            datetime.date(2026, 10, 13), _NOW
        ))

    def test_uses_naver_summary_without_full_article_fetch(self):
        items = [
            _item("뉴욕증시, 나스닥 다우 하락 마감", "2026-10-13T20:20:00+00:00",
                  "https://example.com/one", "금리 전망과 기술주 하락을 전했다."),
            _item("미국 증시 마감, 반도체 약세", "2026-10-14T00:20:00+00:00",
                  "https://example.com/two", "반도체 업종의 낙폭을 설명했다."),
            _item("코스피, 미국 증시 영향에 하락 마감", "2026-10-13T22:20:00+00:00",
                  "https://example.com/korea"),
            _item("뉴욕증시 장중 급락", "2026-10-13T22:00:00+00:00",
                  "https://example.com/intraday"),
            _item("뉴욕증시, 상승 마감", "2026-10-12T20:00:00+00:00",
                  "https://example.com/old"),
        ]
        with patch.object(subject.naver_news, "is_configured", return_value=True), patch.object(
            subject, "_fetch_queries", return_value=items
        ) as fetch, patch(
            "backend.services.news_detail.read_selected_article_details"
        ) as read_body:
            result = subject.build_us_market_close_news_result(now=_NOW)
            cached = subject.build_us_market_close_news_result(limit=1, now=_NOW)
            internal = subject.build_us_market_close_news_result(now=_NOW, include_body=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["session_date"], "2026-10-13")
        self.assertEqual([row["url"] for row in result["items"]],
                         ["https://example.com/two", "https://example.com/one"])
        self.assertEqual(result["items"][0]["description"],
                         "반도체 업종의 낙폭을 설명했다.")
        self.assertEqual(len(cached["items"]), 1)
        self.assertEqual(internal["items"], result["items"])
        self.assertEqual(result["items"][0]["detail_source"], "naver_news_metadata")
        self.assertNotIn("article_body", result["items"][0])
        fetch.assert_called_once_with(subject._QUERIES, category="미국장 마감", per_query=10)
        read_body.assert_not_called()

    def test_deduplicates_headlines_and_skips_unsafe_links(self):
        items = [
            _item("뉴욕증시, 하락 마감", "2026-10-13T20:20:00+00:00",
                  "https://example.com/a"),
            _item("뉴욕증시, 하락 마감", "2026-10-13T20:30:00+00:00",
                  "https://example.com/b"),
            _item("미국 증시, 반등 마감", "2026-10-13T20:40:00+00:00",
                  "javascript:alert(1)"),
        ]
        with patch.object(subject.naver_news, "is_configured", return_value=True), patch.object(
            subject, "_fetch_queries", return_value=items
        ):
            result = subject.build_us_market_close_news_result(now=_NOW)
        self.assertEqual([row["url"] for row in result["items"]], ["https://example.com/b"])

    def test_limits_to_four_and_does_not_expand_provider_calls(self):
        items = [
            _item("뉴욕증시, 마감 보고 %d" % i,
                  "2026-10-13T20:20:00+00:00", "https://example.com/%d" % i)
            for i in range(12)
        ]
        with patch.object(subject.naver_news, "is_configured", return_value=True), patch.object(
            subject, "_fetch_queries", return_value=items
        ) as fetch:
            result = subject.build_us_market_close_news_result(limit=20, now=_NOW)
        self.assertEqual(len(result["items"]), 4)
        fetch.assert_called_once()

    def test_missing_credentials_does_not_fetch(self):
        with patch.object(subject.naver_news, "is_configured", return_value=False), patch.object(
            subject, "_fetch_queries"
        ) as fetch:
            result = subject.build_us_market_close_news_result(now=_NOW)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "source_not_configured")
        fetch.assert_not_called()

if __name__ == "__main__":
    unittest.main()
