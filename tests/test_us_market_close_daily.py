"""Scheduled US close: KST clock, no-duplicate inserts and market-holiday safety."""
import datetime
import unittest
from unittest.mock import patch

from backend.services import us_market_close_daily as job

UTC = datetime.timezone.utc
READY = {
    "ok": True,
    "session_date": "2026-10-13",
    "indices": [
        {"name": name, "date": "2026-10-13", "change_pct": -0.2}
        for name in ("나스닥", "S&P500", "다우")
    ],
    "article_sources": [{"url": "https://example.com/us-market-close"}],
    "sections": [{"title": "주요 지수", "content": "확인된 수치"}],
}


class USMarketCloseDailyTests(unittest.TestCase):
    def test_schedule_is_kst_7am_tuesday_to_saturday(self):
        with patch.object(job, "is_store_configured", return_value=True), patch.object(
            job, "get_us_close_brief_for_session", return_value={"ok": True}
        ) as stored:
            first = job.run_once(now=datetime.datetime(2026, 10, 13, 22, tzinfo=UTC))
            self.assertEqual(first, {"status": "already_saved", "session_date": "2026-10-13"})
            self.assertEqual(stored.call_count, 1)
            self.assertEqual(job.run_once(now=datetime.datetime(2026, 10, 13, 21, tzinfo=UTC)), {"status": "outside_schedule"})
            self.assertEqual(job.run_once(now=datetime.datetime(2026, 10, 17, 22, tzinfo=UTC)), {"status": "outside_schedule"})

    def test_duplicate_run_does_not_collect(self):
        with patch.object(job, "is_store_configured", return_value=True), patch.object(
            job, "get_us_close_brief_for_session", return_value={"ok": True}
        ), patch.object(job, "build_us_market_close_brief") as build:
            result = job.run_once(now=datetime.datetime(2026, 10, 13, 22, tzinfo=UTC))
        self.assertEqual(result["status"], "already_saved")
        build.assert_not_called()

    def test_complete_brief_saved_once(self):
        now = datetime.datetime(2026, 10, 13, 22, tzinfo=UTC)
        with patch.object(job, "is_store_configured", return_value=True), patch.object(
            job, "get_us_close_brief_for_session", return_value=None
        ), patch.object(
            job, "build_us_market_close_brief", return_value=READY
        ) as build, patch.object(job, "save_us_close_brief", return_value=True) as save:
            result = job.run_once(now=now)
        self.assertEqual(result, {"status": "saved", "session_date": "2026-10-13"})
        build.assert_called_once_with(now=now)
        save.assert_called_once_with(READY)

    def test_holiday_and_incomplete_data_never_save(self):
        now = datetime.datetime(2026, 10, 13, 22, tzinfo=UTC)
        for incomplete in (
            {**READY, "indices": []},
            {**READY, "article_sources": []},
            {**READY, "ok": False},
        ):
            with self.subTest(incomplete=incomplete), patch.object(
                job, "is_store_configured", return_value=True
            ), patch.object(
                job, "get_us_close_brief_for_session", return_value=None
            ), patch.object(
                job, "build_us_market_close_brief", return_value=incomplete
            ), patch.object(job, "save_us_close_brief") as save:
                self.assertEqual(job.run_once(now=now)["status"], "incomplete")
                save.assert_not_called()

    def test_unconfigured_does_not_fetch(self):
        with patch.object(job, "is_store_configured", return_value=False), patch.object(
            job, "build_us_market_close_brief"
        ) as build:
            self.assertEqual(
                job.run_once(now=datetime.datetime(2026, 10, 13, 22, tzinfo=UTC)),
                {"status": "not_configured"},
            )
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
