"""No-network regression tests for isolated Alpaca NVDA market-data probe."""
import datetime as dt
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend import alpaca_probe as probe

NY = ZoneInfo("America/New_York")


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        return json.dumps({
            "symbol": "NVDA",
            "bars": [{"t": "2026-10-19T12:17:00Z", "c": 196.25, "v": 120}],
        }).encode()


class AlpacaProbeTests(unittest.TestCase):
    def test_before_premarket_uses_prior_session(self):
        day, start, end = probe._window(dt.datetime(2026, 10, 20, 4, 10, tzinfo=NY))
        self.assertEqual(str(day), "2026-10-19")
        self.assertEqual(start.hour, 4)
        self.assertEqual(end.strftime("%H:%M"), "09:29")

    def test_during_premarket_keeps_20_minute_delay(self):
        day, start, end = probe._window(dt.datetime(2026, 10, 20, 4, 55, tzinfo=NY))
        self.assertEqual(str(day), "2026-10-20")
        self.assertEqual(end.strftime("%H:%M"), "04:35")

    def test_only_nvda_data_get_one_request(self):
        sent = []
        def mocked_urlopen(req, timeout):
            sent.append(req)
            return FakeResponse()
        frozen_now = dt.datetime(2026, 10, 20, 4, 10, tzinfo=NY)
        original_datetime = probe.dt.datetime
        class Clock(original_datetime):
            @classmethod
            def now(cls, tz=None):
                return frozen_now.astimezone(tz)
        with patch.dict(os.environ, {
            "APCA_API_KEY_ID": "FAKE_NONLIVE_KEY",
            "APCA_API_SECRET_KEY": "FAKE_NONLIVE_SECRET",
        }), patch.object(probe.dt, "datetime", Clock), patch.object(
            probe.urllib.request, "urlopen", side_effect=mocked_urlopen
        ), redirect_stdout(io.StringIO()) as output:
            result = probe.main()
        self.assertEqual(result, 0)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].get_method(), "GET")
        self.assertIn("/v2/stocks/NVDA/bars?", sent[0].full_url)
        self.assertIn("feed=sip", sent[0].full_url)
        self.assertIn("ALPACA_NVDA_PREMARKET_OK=", output.getvalue())
        self.assertNotIn("FAKE_NONLIVE", output.getvalue())


if __name__ == "__main__":
    unittest.main()
