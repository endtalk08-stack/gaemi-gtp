import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.us_move_news as job

OPEN = dt.datetime(2026, 11, 25, 15, 0, tzinfo=dt.timezone.utc)      # 10:00 New York


class EventsTest(unittest.TestCase):
    def test_crossing_levels_and_fading(self):
        done = set()
        self.assertEqual(job.events("엔비디아", 1.5, 2.4, done), [("up2", "엔비디아, 2% 넘게 상승")])
        self.assertEqual(job.events("엔비디아", 2.4, 5.1, done), [("up5", "엔비디아, 5% 넘게 상승")])
        self.assertEqual(job.events("엔비디아", 5.1, 1.6, done),
                         [("fade_up", "엔비디아, 상승폭 축소…2% 미만으로 후퇴")])
        self.assertEqual(job.events("엔비디아", 1.6, 2.2, done), [])        # once per day
        self.assertEqual(job.events("엔비디아", 1.2, -0.5, done), [("turn_down", "엔비디아, 하락 전환")])

    def test_hovering_on_a_line_does_not_repeat_or_fade_early(self):
        done = {"up2"}
        self.assertEqual(job.events("애플", 2.1, 1.9, done), [])          # inside the 0.3%p margin

    def test_down_moves(self):
        done = set()
        self.assertEqual(job.events("테슬라", -1.0, -2.5, done), [("down2", "테슬라, 2% 넘게 하락")])
        self.assertEqual(job.events("테슬라", -2.5, -1.5, done),
                         [("fade_down", "테슬라, 하락폭 축소…-2% 이내로 회복")])


class RunTest(unittest.TestCase):
    def setUp(self):
        self.state = Path(tempfile.mkdtemp()) / "state.json"
        self.uploads = []

    def run_at(self, now, pct):
        with patch.object(job, "us_trading_day", return_value=dt.date(2026, 11, 25)):
            return job.run(now, top20=lambda: [{"symbol": "NVDA", "name": "엔비디아", "change_pct": pct}],
                           upload=lambda payload, key: self.uploads.append((key, payload)), state_path=self.state)

    def test_first_check_only_records_then_publishes_moves(self):
        self.assertEqual(self.run_at(OPEN, 3.0)["status"], "unchanged")    # no headline at first sight
        self.assertEqual(self.run_at(OPEN + dt.timedelta(minutes=1), 5.4)["new"], 1)
        key, payload = self.uploads[0]
        self.assertEqual(key, "news/stocks/us/MOVEFEED.json")
        self.assertEqual(payload["items"][0]["title"], "엔비디아, 5% 넘게 상승")
        self.assertEqual(payload["items"][0]["symbol"], "NVDA")

    def test_outside_regular_hours_nothing_happens(self):
        self.assertEqual(self.run_at(dt.datetime(2026, 11, 25, 22, 0, tzinfo=dt.timezone.utc), 3.0)["status"], "closed")
        self.assertEqual(self.uploads, [])


if __name__ == "__main__":
    unittest.main()
