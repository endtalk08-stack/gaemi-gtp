import importlib.util
import pathlib
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

PATH = pathlib.Path(__file__).resolve().parents[1] / "ops" / "staged_daily_issue_schedule.py"
spec = importlib.util.spec_from_file_location("staged_daily_issue_schedule", PATH)
schedule = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schedule)
KST = ZoneInfo("Asia/Seoul")


class DailyScheduleTests(unittest.TestCase):
    def test_summer_kst_time(self):
        self.assertEqual(schedule.scheduled_kst_time(datetime(2026, 10, 17).date()).strftime("%Y-%m-%d %H:%M"),
                         "2026-10-17 23:30")

    def test_winter_kst_time(self):
        self.assertEqual(schedule.scheduled_kst_time(datetime(2026, 11, 2).date()).strftime("%Y-%m-%d %H:%M"),
                         "2026-11-03 00:30")

    def test_summer_once(self):
        t = datetime(2026, 10, 17, 23, 31, tzinfo=KST)
        self.assertEqual(schedule.due_run(t, []), "2026-10-17")
        self.assertIsNone(schedule.due_run(t, ["2026-10-17"]))

    def test_winter_once_after_midnight(self):
        t = datetime(2026, 11, 3, 0, 31, tzinfo=KST)
        self.assertEqual(schedule.due_run(t, []), "2026-11-02")
        self.assertIsNone(schedule.due_run(t, ["2026-11-02"]))

    def test_window_boundaries_summer(self):
        self.assertIsNone(schedule.due_run(datetime(2026, 10, 17, 23, 29, tzinfo=KST), []))
        self.assertEqual(schedule.due_run(datetime(2026, 10, 17, 23, 30, tzinfo=KST), []), "2026-10-17")
        self.assertEqual(schedule.due_run(datetime(2026, 10, 17, 23, 59, tzinfo=KST), []), "2026-10-17")
        self.assertIsNone(schedule.due_run(datetime(2026, 10, 18, 0, 0, tzinfo=KST), []))

    def test_window_boundaries_winter(self):
        self.assertIsNone(schedule.due_run(datetime(2026, 11, 3, 0, 29, tzinfo=KST), []))
        self.assertEqual(schedule.due_run(datetime(2026, 11, 3, 0, 30, tzinfo=KST), []), "2026-11-02")
        self.assertEqual(schedule.due_run(datetime(2026, 11, 3, 0, 59, tzinfo=KST), []), "2026-11-02")
        self.assertIsNone(schedule.due_run(datetime(2026, 11, 3, 1, 0, tzinfo=KST), []))

    def test_weekend_is_not_skipped(self):
        self.assertEqual(schedule.due_run(datetime(2026, 10, 18, 23, 31, tzinfo=KST), []), "2026-10-18")

    def test_dst_transition_day(self):
        self.assertEqual(schedule.scheduled_kst_time(datetime(2026, 11, 1).date()).strftime("%Y-%m-%d %H:%M"), "2026-11-02 00:30")

    def test_outside_window(self):
        self.assertIsNone(schedule.due_run(datetime(2026, 11, 3, 1, 30, tzinfo=KST), []))


if __name__ == "__main__":
    unittest.main()
