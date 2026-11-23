import datetime as dt
import tempfile
import json
import time
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend import us_quote_change as baseline
from backend import kiwoom_us_top20_api as api


class VerifiedQuoteChangeTests(unittest.TestCase):
    def setUp(self):
        baseline._CACHE.clear()

    def test_monday_day_market_uses_friday_regular_close(self):
        monday = dt.datetime(2026, 11, 23, 11, tzinfo=ZoneInfo("America/New_York"))
        expected = dt.date(2026, 11, 20)
        self.assertEqual(baseline._target(monday), (dt.date(2026, 11, 22), False))
        payload = {"chart": {"error": None, "result": [{
            "meta": {"symbol": "QQQ", "currency": "USD", "exchangeTimezoneName": "America/New_York"},
            "timestamp": [int(dt.datetime(2026, 11, 20, 9, 30, tzinfo=dt.timezone(dt.timedelta(hours=-5))).timestamp())],
            "indicators": {"quote": [{"close": [608.45]}]},
        }]}}
        with patch.object(baseline.urllib.request, "urlopen", return_value=BytesIO(json.dumps(payload).encode())) as fetch:
            self.assertEqual(baseline._lookup("QQQ", "ND", monday.date() - dt.timedelta(days=1), False),
                             (608.45, expected.isoformat()))
            self.assertEqual(fetch.call_count, 1)
        with patch.object(baseline, "_POOL") as pool:
            from concurrent.futures import Future
            completed = Future()
            completed.set_result((608.45, expected.isoformat()))
            pool.submit.return_value = completed
            baseline.validated_change("QQQ", "ND", 625.31, now=monday)
            percent, date = baseline.validated_change("QQQ", "ND", 625.31, now=monday)
        self.assertAlmostEqual(percent, 2.771, places=2)
        self.assertEqual(date, "2026-11-20")
        pool.submit.assert_called_once()

    def test_after_close_never_substitutes_old_session(self):
        friday = dt.datetime(2026, 11, 20, 16, 5, tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(baseline._target(friday), (friday.date(), True))
        with patch.object(baseline.urllib.request, "urlopen", side_effect=OSError("unavailable")) as fetch:
            self.assertIsNone(baseline._lookup("QQQ", "ND", friday.date(), True))
            fetch.assert_called_once()

    def test_unverified_stream_and_ranking_do_not_show_percentage(self):
        api._set_top20_symbols({"NVDA"})
        api._publish_live_quote({"symbol": "NVDA", "price": 100, "change_pct": -9.55})
        self.assertIsNone(api._top20_snapshot()[0]["change_pct"])
        api._publish_live_quote({"symbol": "NVDA", "price": 105, "change_pct": 5,
                                 "reference_close_date": "2026-11-20"})
        self.assertEqual(api._top20_snapshot()[0]["change_pct"], 5)
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "ranking.json"
            file.write_text(json.dumps({"schema_version": 1, "source": "kiwoom", "market": "US",
                "rank_type": "trading_value", "items": [
                    {"rank": n, "symbol": f"T{n}", "name": f"Test {n}",
                     "change_pct": -9.55} for n in range(1, 21)]}), encoding="utf-8")
            self.assertTrue(all(row["change_pct"] is None for row in api.read_top20(file)["items"]))


if __name__ == "__main__":
    unittest.main()
