"""US market close collection is isolated from per-stock news flows."""
import datetime
import unittest
from unittest.mock import patch

from backend.services import us_market_close_news as subject


_NOW = datetime.datetime(2026, 10, 14, 7, tzinfo=datetime.timezone.utc)


def _item(title, published_at, url="https://example.com/market"):
    return {
        "title": title,
        "description": "뉴욕증시는 이날 상승 마감했다.",
        "published_at": published_at,
        "url": url,
        "source": "예시",
    }


class USMarketCloseNewsTests(unittest.TestCase):
    def setUp(self):
        subject._CACHE = None
        subject._CACHED_AT = 0

    def tearDown(self):
        subject._CACHE = None
        subject._CACHED_AT = 0

    def test_new_york_close_is_previous_day_in_korea_morning(self):
        self.assertEqual(subject._last_completed_session(_NOW).isoformat(), "2026-10-13")
        self.assertEqual(
            subject._last_completed_session(
                datetime.datetime(2026, 10, 18, 15, tzinfo=datetime.timezone.utc)
            ).isoformat(),
            "2026-10-16",
        )

    def test_filters_out_preclose_domestic_and_old_news(self):
        rows = [
            _item("뉴욕증시, 나스닥 상승 마감", "2026-10-13T20:20:00+00:00", "https://example.com/1"),
            _item("뉴욕증시, 다우 강세로 장을 마쳐", "2026-10-14T00:20:00+00:00", "https://example.com/2"),
            _item("뉴욕증시, 나스닥 상승 출발", "2026-10-13T20:30:00+00:00", "https://example.com/3"),
            _item("코스피, 뉴욕증시 강세에 상승 마감", "2026-10-13T20:40:00+00:00", "https://example.com/4"),
            _item("뉴욕증시, 나스닥 상승 마감", "2026-10-12T20:20:00+00:00", "https://example.com/5"),
            _item("뉴욕증시, 나스닥 상승 마감", "2026-10-13T19:59:00+00:00", "https://example.com/6"),
        ]
        with patch.object(subject.naver_news, "is_configured", return_value=True), patch.object(
            subject, "_fetch_queries", return_value=rows
        ) as fetch:
            result = subject.build_us_market_close_news_result(limit=12, now=_NOW)
            again = subject.build_us_market_close_news_result(limit=1, now=_NOW)

        self.assertTrue(result["ok"])
        self.assertEqual(result["session_date"], "2026-10-13")
        self.assertEqual(
            [item["url"] for item in result["items"]],
            ["https://example.com/1", "https://example.com/2"],
        )
        self.assertEqual(len(again["items"]), 1)
        self.assertEqual(again["items"][0]["news_scope"], "market_close")
        fetch.assert_called_once_with(subject._QUERIES, category="미국장 마감", per_query=15)

    def test_missing_credentials_does_not_reuse_cached_result(self):
        with patch.object(subject.naver_news, "is_configured", return_value=False), patch.object(
            subject, "_fetch_queries"
        ) as fetch:
            result = subject.build_us_market_close_news_result(now=_NOW)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "source_not_configured")
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
