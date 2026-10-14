"""US market close news uses few verified, complementary original articles."""
import datetime
import unittest
from unittest.mock import patch

from backend.services import us_market_close_news as subject


_NOW = datetime.datetime(2026, 10, 14, 7, tzinfo=datetime.timezone.utc)
_MAIN_BODY = (
    "미국 뉴욕증시에서 나스닥과 다우, S&P500 지수는 상승세로 거래를 마쳤다. "
    "반도체 업종은 AI 관련 기업 실적 발표의 영향으로 강세를 보였다. "
    "엔비디아 등 주요 반도체 기업이 상승했다. "
    "미국 국채금리가 내려가고 연준의 향후 금리 결정에 대한 기대가 커졌다. "
    "투자자들은 발표된 기업 실적을 소화하며 거래를 마무리했다."
)
_FALLING_BODY = (
    "전기차 업종은 판매 둔화 우려로 약세를 보였다. "
    "에너지 관련 업종도 국제유가 하락의 여파로 약세를 나타냈다. "
    "연준의 금리 정책 전망과 국채금리 변화가 시장 투자심리에 영향을 줬다. "
    "일부 개별 기업은 예상보다 낮은 분기 실적을 발표했다. "
    "시장에서는 수요 둔화에 대한 경계심도 이어졌으며 관련 기업들의 향후 실적 전망에도 관심이 쏠렸다."
)


def _item(title, published_at, url="https://example.com/market"):
    return {
        "title": title,
        "description": "뉴욕증시는 이날 상승 마감했다.",
        "published_at": published_at,
        "url": url,
        "source": "예시",
    }


def _details_for(rows, limit, with_sources):
    assert with_sources
    assert limit == len(rows)
    bodies = {
        "https://example.com/1": _MAIN_BODY,
        "https://example.com/2": _FALLING_BODY,
        "https://example.com/3": _MAIN_BODY,
    }
    return [
        {
            "text": bodies.get(row["url"], ""),
            "source": "jsonld_article_body" if row["url"] in bodies else "meta_description",
        }
        for row in rows
    ]


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

    def test_selects_verified_articles_that_fill_missing_information(self):
        rows = [
            _item("뉴욕증시, 나스닥 다우 상승 마감", "2026-10-13T20:20:00+00:00", "https://example.com/1"),
            _item("뉴욕증시, 업종별 희비로 장을 마쳐", "2026-10-14T00:20:00+00:00", "https://example.com/2"),
            _item("뉴욕증시, 상승 마감 속 장중 거래", "2026-10-13T22:30:00+00:00", "https://example.com/3"),
            _item("코스피, 뉴욕증시 강세에 상승 마감", "2026-10-13T20:40:00+00:00", "https://example.com/4"),
            _item("뉴욕증시, 상승 마감", "2026-10-12T20:20:00+00:00", "https://example.com/5"),
            _item("뉴욕증시, 상승 마감", "2026-10-13T19:59:00+00:00", "https://example.com/6"),
        ]
        with patch.object(subject.naver_news, "is_configured", return_value=True), patch.object(
            subject, "_fetch_queries", return_value=rows
        ) as fetch, patch(
            "backend.services.news_detail.read_selected_article_details",
            side_effect=_details_for,
        ) as details:
            result = subject.build_us_market_close_news_result(now=_NOW)
            cached = subject.build_us_market_close_news_result(limit=1, now=_NOW)
            internal = subject.build_us_market_close_news_result(now=_NOW, include_body=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["session_date"], "2026-10-13")
        self.assertEqual(
            [item["url"] for item in result["items"]],
            ["https://example.com/1", "https://example.com/2"],
        )
        self.assertEqual(len(cached["items"]), 1)
        self.assertEqual(cached["items"][0]["news_scope"], "market_close")
        self.assertNotIn("article_body", result["items"][0])
        self.assertEqual(internal["items"][0]["article_body"], _MAIN_BODY)
        self.assertEqual(
            set().union(*(set(x["information_coverage"]) for x in result["items"])),
            {"indices", "rising_sectors", "falling_sectors", "market_factors"},
        )
        fetch.assert_called_once_with(subject._QUERIES, category="미국장 마감", per_query=10)
        details.assert_called_once()

    def test_unverified_article_and_duplicate_information_are_not_kept(self):
        rows = [
            _item("뉴욕증시, 나스닥 다우 상승 마감", "2026-10-13T20:20:00+00:00", "https://example.com/1"),
            _item("뉴욕증시, 나스닥 다우 상승 마감", "2026-10-13T20:10:00+00:00", "https://example.com/3"),
            _item("뉴욕증시, 나스닥 다우 상승 마감", "2026-10-13T20:30:00+00:00", "https://example.com/7"),
        ]
        with patch.object(subject.naver_news, "is_configured", return_value=True), patch.object(
            subject, "_fetch_queries", return_value=rows
        ), patch(
            "backend.services.news_detail.read_selected_article_details",
            side_effect=_details_for,
        ):
            result = subject.build_us_market_close_news_result(now=_NOW)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["url"], "https://example.com/1")

    def test_search_and_body_reads_are_bounded(self):
        rows = [
            _item("뉴욕증시, 나스닥 다우 상승 마감", "2026-10-13T20:20:00+00:00", f"https://example.com/{i}")
            for i in range(10)
        ]
        with patch.object(subject.naver_news, "is_configured", return_value=True), patch.object(
            subject, "_fetch_queries", return_value=rows
        ), patch(
            "backend.services.news_detail.read_selected_article_details",
            side_effect=_details_for,
        ) as details:
            result = subject.build_us_market_close_news_result(limit=20, now=_NOW)
        self.assertLessEqual(len(result["items"]), 4)
        self.assertEqual(len(details.call_args.args[0]), 6)

    def test_missing_credentials_does_not_fetch_news(self):
        with patch.object(subject.naver_news, "is_configured", return_value=False), patch.object(
            subject, "_fetch_queries"
        ) as fetch:
            result = subject.build_us_market_close_news_result(now=_NOW)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "source_not_configured")
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
