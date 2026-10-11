"""Regression tests for date-aware prior-session facts shared with private chat."""
import datetime
import io
import json
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend.providers.market_price import DAILY_HISTORY_CACHE, fetch_daily_price_history
from backend.services.stock_analysis import _previous_trading_day
from backend.services.ai_test import _context, _previous_day_reply


class PreviousTradingDayTests(unittest.TestCase):
    def tearDown(self):
        DAILY_HISTORY_CACHE.pop("005930.KS", None)

    def _daily_chart(self, *, include_dates=True):
        zone = ZoneInfo("Asia/Seoul")
        data = {
            "chart": {"result": [{
                "meta": {"exchangeTimezoneName": "Asia/Seoul"},
                "indicators": {"quote": [{
                    "close": [100, 110, 120],
                    "high": [104, 115, 123],
                    "low": [98, 105, 118],
                    "volume": [1000, 1200, 1400]
                }]},
            }]}
        }
        if include_dates:
            data["chart"]["result"][0]["timestamp"] = [
                int(datetime.datetime(2026, 10, day, 9, tzinfo=zone).timestamp())
                for day in (7, 8, 12)
            ]
        return data

    def test_daily_history_preserves_exchange_local_dates(self):
        payload = json.dumps(self._daily_chart()).encode("utf-8")
        with patch("backend.providers.market_price.urllib.request.urlopen", return_value=io.BytesIO(payload)):
            rows = fetch_daily_price_history("005930.KS")
        self.assertEqual([row["date"] for row in rows], ["2026-10-07", "2026-10-08", "2026-10-12"])
        self.assertEqual(rows[-1]["volume"], 1400.0)
        result = _previous_trading_day(rows, is_krw=True, as_of_date=datetime.date(2026, 10, 12))
        self.assertEqual(result, {"date": "2026-10-08", "high": 115.0, "close": 110.0, "change_pct": 10.0})

    def test_missing_timestamps_does_not_remove_original_ohlcv_rows(self):
        payload = json.dumps(self._daily_chart(include_dates=False)).encode("utf-8")
        with patch("backend.providers.market_price.urllib.request.urlopen", return_value=io.BytesIO(payload)):
            rows = fetch_daily_price_history("005930.KS")
        self.assertEqual(len(rows), 3)
        self.assertNotIn("date", rows[-1])
        self.assertIsNone(_previous_trading_day(rows, is_krw=True, as_of_date=datetime.date(2026, 10, 12)))

    def test_previous_session_when_latest_bar_not_yet_available(self):
        rows = [
            {"date": "2026-10-07", "close": 100, "high": 105},
            {"date": "2026-10-08", "close": 110, "high": 115},
        ]
        result = _previous_trading_day(rows, is_krw=True, as_of_date=datetime.date(2026, 10, 12))
        self.assertEqual(result["date"], "2026-10-08")
        self.assertEqual(result["change_pct"], 10.0)

    def test_us_market_uses_its_own_session_date(self):
        rows = [
            {"date": "2026-10-08", "close": 100, "high": 104},
            {"date": "2026-10-09", "close": 95, "high": 99},
            {"date": "2026-10-12", "close": 96, "high": 98},
        ]
        result = _previous_trading_day(rows, is_krw=False, as_of_date=datetime.date(2026, 10, 12))
        self.assertEqual(result, {"date": "2026-10-09", "high": 99.0, "close": 95.0, "change_pct": -5.0})

    def test_private_chat_prior_day_answers_are_dated_and_distinct(self):
        metrics = {
            "current": 120, "change_pct": 9.09, "currency": "KRW",
            "previous_trading_day": {"date": "2026-10-08", "high": 115.0, "close": 110, "change_pct": 10.0}
        }
        self.assertEqual(
            _previous_day_reply("전일 최고가 얼마야?", metrics),
            "전 거래일(2026-10-08) 기준 최고가 115원.",
        )
        self.assertEqual(
            _previous_day_reply("전일 몇 프로 올랐어?", metrics),
            "전 거래일(2026-10-08) 기준 그날의 등락률 +10.00% (상승).",
        )
        self.assertIsNone(_previous_day_reply("오늘 전일 대비 몇 프로야?", metrics))
        self.assertIsNone(_previous_day_reply("어제 뉴스 알려줘", metrics))

    def test_no_history_or_missing_prior_close_is_not_guessed(self):
        self.assertEqual(
            _previous_day_reply("전일 최고가 얼마야?", {"current": 120}),
            "전 거래일의 날짜가 확인된 시세 데이터가 없어.",
        )
        result = _previous_trading_day(
            [{"date": "2026-10-08", "close": 110, "high": 115}],
            is_krw=True,
            as_of_date=datetime.date(2026, 10, 12),
        )
        self.assertNotIn("change_pct", result)
        self.assertIn("자료 없음", _previous_day_reply("전일 몇 프로 올랐어?", {"previous_trading_day": result}))

    def test_shared_context_keeps_news_disclosures_and_price_metrics(self):
        previous = {"date": "2026-10-08", "high": 115, "close": 110, "change_pct": 10}
        data = {
            "sections": [{"id": "why-up", "content": "현재 주가는 120원 기록 중!"}],
            "price_snapshot": {"current": 120, "change_pct": 9.09, "previous_trading_day": previous},
            "paired_news_items": [{"title": "기사 제목", "description": "요약", "published_at": "2026-10-08"}],
            "disclosures": [{"title": "공시 제목", "date": "2026-10-08"}],
            "issue_briefs": [],
        }
        context = _context("삼성전자", data)
        self.assertEqual(context["price_metrics"]["previous_trading_day"], previous)
        self.assertEqual(context["news"][0]["title"], "기사 제목")
        self.assertEqual(context["official_disclosures"][0]["title"], "공시 제목")


if __name__ == "__main__":
    unittest.main()
