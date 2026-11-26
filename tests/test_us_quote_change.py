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
        baseline._OFFICIAL_CACHE.clear()

    def test_regular_close_hold_uses_dated_close_then_switches_off(self):
        from concurrent.futures import Future
        hold = dt.datetime(2026, 11, 23, 16, 5, tzinfo=ZoneInfo("America/New_York"))
        after = hold.replace(minute=30)
        completed = Future()
        completed.set_result((102.5, 2.5, "2026-11-20"))
        with patch.object(baseline, "_POOL") as pool:
            pool.submit.return_value = completed
            quote = baseline.official_close_quote("QQQ", "ND", now=hold)
        self.assertEqual(quote["price"], 102.5)
        self.assertEqual(quote["change_pct"], 2.5)
        self.assertEqual(quote["reference_close_date"], "2026-11-20")
        self.assertIsNone(baseline.official_close_quote("QQQ", "ND", now=after))

    def test_dated_close_cannot_use_a_different_day(self):
        from backend.providers import kiwoom_us_quotes
        with patch.object(kiwoom_us_quotes, "fetch_us_close", return_value={
                "session_date": "2026-11-20", "close": 102.5}), \
             patch.object(baseline, "_lookup") as lookup:
            self.assertIsNone(baseline._read_official_close("QQQ", "ND", dt.date(2026, 11, 23)))
            lookup.assert_not_called()

    def test_new_session_uses_dated_regular_close_when_chart_lags(self):
        from backend.providers import kiwoom_us_quotes
        now = dt.datetime(2026, 11, 23, 16, 30, tzinfo=ZoneInfo("America/New_York"))
        with patch.object(baseline, "_lookup", return_value=None), \
             patch.object(kiwoom_us_quotes, "fetch_us_close", return_value={
                 "session_date": "2026-11-23", "close": 100.0}):
            self.assertEqual(baseline._verified_baseline("QQQ", "ND", now.date(), True),
                             (100.0, "2026-11-23"))
        from concurrent.futures import Future
        completed = Future()
        completed.set_result((100.0, "2026-11-23"))
        with patch.object(baseline, "_POOL") as pool:
            pool.submit.return_value = completed
            _, _ = baseline.validated_change("QQQ", "ND", 102.0, now=now)
            rate, date = baseline.validated_change("QQQ", "ND", 102.0, now=now)
        self.assertAlmostEqual(rate, 2.0)
        self.assertEqual(date, "2026-11-23")

    def test_market_snapshot_holds_close_without_live_tick(self):
        hold = dt.datetime(2026, 11, 23, 16, 5, tzinfo=ZoneInfo("America/New_York"))
        official = {"symbol": "QQQ", "exchange": "ND", "price": 102.5,
                    "change_pct": 2.5, "reference_close_date": "2026-11-20",
                    "received_at_ms": int(hold.timestamp() * 1000),
                    "stale": False, "source": "kiwoom:regular-close"}
        with patch.object(baseline, "official_close_quote", return_value=official):
            self.assertEqual(api._us_close_get("QQQ", now=hold, exchange="ND"), official)

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

    def test_last_verified_quote_restores_after_restart_on_holiday_and_weekend(self):
        observed = dt.datetime(2026, 11, 25, 15, 58, tzinfo=ZoneInfo("America/New_York"))
        record = {
            "day": "2026-11-25",
            "items": {
                "NVDA": {
                    "symbol": "NVDA", "price": 190.0, "change_pct": 2.75,
                    "reference_close_date": "2026-11-24",
                    "received_at_ms": int(observed.timestamp() * 1000),
                    "observed_at_ms": int(observed.timestamp() * 1000),
                    "exchange": "ND",
                }
            },
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "last-verified.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            old_file, old_cache = api._US_CLOSE_FILE, api._US_CLOSE_CACHE
            old_read = api._US_CLOSE_LAST_READ
            try:
                api._US_CLOSE_FILE = path
                api._US_CLOSE_CACHE = {"day": "", "items": {}}
                api._US_CLOSE_LAST_READ = 0.0
                self.assertEqual(api._us_close_read_disk(), record)
                api._us_close_merge(record)
                self.assertEqual(api._US_CLOSE_CACHE["day"], "2026-11-25")
                self.assertIn("NVDA", api._US_CLOSE_CACHE["items"])
                api._US_CLOSE_CACHE = {"day": "", "items": {}}
                api._US_CLOSE_LAST_READ = 0.0
                for now in (
                    dt.datetime(2026, 11, 26, 10, 0, tzinfo=ZoneInfo("America/New_York")),
                    dt.datetime(2026, 11, 28, 12, 0, tzinfo=ZoneInfo("America/New_York")),
                ):
                    quote = api._us_close_get("NVDA", now=now, exchange="ND")
                    self.assertEqual(quote["price"], 190.0)
                    self.assertEqual(quote["change_pct"], 2.75)
                    self.assertTrue(quote["stale"])
                    self.assertEqual(quote["reference_close_date"], "2026-11-24")
            finally:
                api._US_CLOSE_FILE = old_file
                api._US_CLOSE_CACHE = old_cache
                api._US_CLOSE_LAST_READ = old_read

    def test_last_verified_quote_is_not_used_during_regular_session(self):
        now = dt.datetime(2026, 11, 25, 11, 0, tzinfo=ZoneInfo("America/New_York"))
        old_cache, old_read = api._US_CLOSE_CACHE, api._US_CLOSE_LAST_READ
        try:
            api._US_CLOSE_CACHE = {"day": "", "items": {}}
            api._US_CLOSE_LAST_READ = 0.0
            with patch.object(api, "_us_close_read_disk", return_value={
                "day": "2026-11-24", "items": {"NVDA": {
                    "symbol": "NVDA", "price": 180.0, "change_pct": 1.0,
                    "reference_close_date": "2026-11-21",
                    "observed_at_ms": int(dt.datetime(2026, 11, 24, 15, 0,
                        tzinfo=ZoneInfo("America/New_York")).timestamp() * 1000),
                }}
            }):
                self.assertIsNone(api._us_close_get("NVDA", now=now, exchange="ND"))
        finally:
            api._US_CLOSE_CACHE, api._US_CLOSE_LAST_READ = old_cache, old_read

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


    def test_closed_session_snapshot_uses_prior_session_baseline(self):
        now = dt.datetime(2026, 11, 26, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        expected_asof = dt.datetime(2026, 11, 25, 15, 59, 59,
                                    tzinfo=ZoneInfo("America/New_York"))
        with patch.object(baseline, "validated_change", return_value=(2.75, "2026-11-24")) as validate:
            result = api._validated_snapshot_change("NVDA", "ND", 190.0, now=now)
        self.assertEqual(result, (2.75, "2026-11-24"))
        self.assertEqual(validate.call_args.kwargs["now"], expected_asof)

    def test_closed_session_snapshot_rejects_old_ranking_capture(self):
        now = dt.datetime(2026, 11, 26, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        captured = dt.datetime(2026, 11, 24, 21, 0, tzinfo=dt.timezone.utc)
        with patch.object(baseline, "validated_change") as validate:
            result = api._validated_snapshot_change(
                "NVDA", "ND", 190.0, now=now, snapshot_at=captured)
        self.assertEqual(result, (None, None))
        validate.assert_not_called()

    def test_top20_uses_kiwoom_source_percent_when_close_lookup_is_unavailable(self):
        rows = [
            {"rank": n, "symbol": f"T{n}", "name": f"Test {n}", "exchange": "ND",
             "price": 100.0 + n, "change_pct": round(n * 0.25, 2)}
            for n in range(1, 21)
        ]
        payload = {"schema_version": 1, "source": "kiwoom", "market": "US",
                   "rank_type": "trading_value", "captured_at": "2026-11-25T22:00:00Z",
                   "items": rows}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ranking.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(api, "_us_close_get", return_value=None), \
                 patch.object(api, "_TOP20_QUOTES", {}), \
                 patch.object(api, "_us_close_phase", return_value=("none", "2026-11-26")), \
                 patch.object(api, "_last_completed_us_session", return_value=dt.date(2026, 11, 25)), \
                 patch.object(api, "_validated_snapshot_change", return_value=(None, None)):
                result = api.read_top20(path)
        self.assertEqual(len(result["items"]), 20)
        self.assertEqual([item["change_pct"] for item in result["items"]],
                         [row["change_pct"] for row in rows])
        self.assertTrue(all(item["reference_close_date"] == "2026-11-24"
                            for item in result["items"]))

if __name__ == "__main__":
    unittest.main()
