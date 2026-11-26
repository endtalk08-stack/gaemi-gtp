"""Regression tests for the 2026-11-26 quote-service fixes.

1. Sector ETF rates show the last completed session's close outside market hours.
2. TOP20 rates survive a ranking file refreshed after the close (holiday,
   weekend, pre-market).
3. Viewer requests never wait behind a slow Kiwoom ETF refresh.
"""
import datetime as dt
import json
import pathlib
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from backend import kiwoom_us_top20_api as api
from backend import us_quote_change
from backend.providers import kiwoom_us_industries as industries

UTC = dt.timezone.utc


def _frozen_datetime(now):
    real = api.datetime

    class Frozen(real):
        @classmethod
        def now(cls, tz=None):
            return now if tz else now.replace(tzinfo=None)

    return Frozen


class _Base(unittest.TestCase):
    def setUp(self):
        api._US_INDUSTRY_ETF_CACHE.clear()
        api._LAST_SESSION_CLOSE.clear()
        api._ETF_QUOTES.clear()
        api._TOP20_QUOTES.clear()
        # Other tests leave verified baselines in the shared close cache.
        us_quote_change._CACHE.clear()
        us_quote_change._OFFICIAL_CACHE.clear()
        self.addCleanup(us_quote_change._CACHE.clear)
        self.addCleanup(api._US_INDUSTRY_ETF_CACHE.clear)
        self.addCleanup(api._LAST_SESSION_CLOSE.clear)


class LastSessionCloseTest(_Base):
    def test_holiday_shows_last_session_close_for_every_sector_etf(self):
        reads = []

        def official(symbol, exchange, day):
            reads.append(day.isoformat())
            return (100.0, -0.45 if symbol == "XLE" else 1.23, "2026-11-24")

        with patch.object(us_quote_change, "_read_official_close", official), \
                patch.object(industries, "fetch_us_etf_quotes", lambda **k: []), \
                patch.object(industries, "fetch_us_etf_exchanges",
                             lambda **k: {s: "NY" for s in industries.ETF_TICKERS}), \
                patch.object(api, "_us_close_get", lambda *a, **k: None), \
                patch.object(api, "_us_close_phase", lambda now=None: ("none", "2026-11-26")), \
                patch.object(api, "_last_completed_us_session", lambda now=None: dt.date(2026, 11, 25)):
            quotes = {q["symbol"]: q for q in api._get_us_industry_etf_quotes()}

        self.assertEqual(set(quotes), set(industries.ETF_TICKERS))
        for quote in quotes.values():
            self.assertIsNotNone(quote["change_pct"])
            self.assertIsNotNone(quote["price"])
            self.assertFalse(quote["stale"])
            self.assertEqual(quote["source"], "kiwoom:last-session-close")
            self.assertEqual(quote["reference_close_date"], "2026-11-24")
        self.assertEqual(quotes["XLE"]["change_pct"], -0.45)
        self.assertEqual(set(reads), {"2026-11-25"})

    def test_no_last_session_fallback_during_regular_session(self):
        regular = dt.datetime(2026, 11, 25, 15, 0, tzinfo=UTC)   # 10:00 ET Wednesday
        self.assertIsNone(api._last_session_close("XLK", "NY", now=regular))

    def test_last_completed_session_skips_weekends_and_holidays(self):
        cases = (
            (dt.datetime(2026, 11, 26, 16, 0, tzinfo=UTC), "2026-11-25"),   # Thanksgiving
            (dt.datetime(2026, 11, 28, 15, 0, tzinfo=UTC), "2026-11-27"),   # Saturday
            (dt.datetime(2026, 11, 30, 13, 0, tzinfo=UTC), "2026-11-27"),   # Monday pre-market
            (dt.datetime(2026, 11, 25, 22, 0, tzinfo=UTC), "2026-11-25"),   # after the close
        )
        for now, expected in cases:
            self.assertEqual(api._last_completed_us_session(now).isoformat(), expected, now)


class Top20RankingFileTest(_Base):
    def _ranking_file(self, captured):
        rows = [{"rank": i, "symbol": symbol, "name": symbol, "exchange": "ND",
                 "price": 100.0 + i, "change_pct": -3.91 if symbol == "NVDA" else 0.5}
                for i, symbol in enumerate(["NVDA"] + ["S%02d" % n for n in range(1, 20)], 1)]
        folder = pathlib.Path(tempfile.mkdtemp())
        path = folder / "ranking.json"
        path.write_text(json.dumps({
            "schema_version": 1, "source": "kiwoom", "market": "US",
            "rank_type": "trading_value", "captured_at": captured.isoformat(), "items": rows,
        }))
        return path

    def _first_row(self, now, captured):
        with patch.object(us_quote_change, "_lookup", lambda *a, **k: None), \
                patch.object(api, "_us_close_get", lambda *a, **k: None), \
                patch.object(api, "datetime", _frozen_datetime(now)):
            return api.read_top20(self._ranking_file(captured))["items"][0]

    def test_rates_kept_when_file_refreshed_after_the_close(self):
        cases = (
            ("holiday", dt.datetime(2026, 11, 26, 15, 40, tzinfo=UTC),
             dt.datetime(2026, 11, 26, 15, 20, tzinfo=UTC), "2026-11-24"),
            ("saturday", dt.datetime(2026, 11, 28, 15, 0, tzinfo=UTC),
             dt.datetime(2026, 11, 28, 14, 0, tzinfo=UTC), "2026-11-25"),
            ("pre-market", dt.datetime(2026, 11, 25, 13, 0, tzinfo=UTC),
             dt.datetime(2026, 11, 25, 12, 0, tzinfo=UTC), "2026-11-23"),
        )
        for name, now, captured, reference in cases:
            row = self._first_row(now, captured)
            self.assertEqual(row["change_pct"], -3.91, name)
            self.assertEqual(row["reference_close_date"], reference, name)

    def test_file_from_before_the_last_close_is_not_used(self):
        row = self._first_row(dt.datetime(2026, 11, 26, 15, 40, tzinfo=UTC),
                              dt.datetime(2026, 11, 25, 16, 0, tzinfo=UTC))
        self.assertIsNone(row["change_pct"])


class EtfRefreshDoesNotBlockViewersTest(_Base):
    def test_viewer_is_served_from_cache_while_background_refresh_runs(self):
        calls = []

        def slow_fetch(symbols=None, **kwargs):
            calls.append(time.monotonic())
            time.sleep(1.0)
            now_ms = int(time.time() * 1000)
            return [{"symbol": s, "price": 10.0, "exchange": "NY", "received_at_ms": now_ms}
                    for s in symbols]

        with patch.object(industries, "fetch_us_etf_quotes", slow_fetch), \
                patch.object(api, "_us_close_get", lambda *a, **k: None), \
                patch.object(api, "_validated_snapshot_change", lambda *a, **k: (1.5, "2026-11-24")), \
                patch.object(api, "_last_session_close", lambda *a, **k: None):
            api._get_us_industry_etf_quotes(background=True)
            warmer = threading.Thread(target=api._get_us_industry_etf_quotes,
                                      kwargs={"background": True})
            warmer.start()
            time.sleep(0.1)
            started = time.monotonic()
            during = api._get_us_industry_etf_quotes()
            during_elapsed = time.monotonic() - started
            warmer.join()

            for key, (_, quote) in list(api._US_INDUSTRY_ETF_CACHE.items()):
                api._US_INDUSTRY_ETF_CACHE[key] = (0.0, quote)   # expire the TTL
            started = time.monotonic()
            expired = api._get_us_industry_etf_quotes()
            expired_elapsed = time.monotonic() - started

        self.assertLess(during_elapsed, 0.5)
        self.assertLess(expired_elapsed, 0.5)
        self.assertEqual(len(calls), 2)       # only the warmer called Kiwoom
        for quotes in (during, expired):
            self.assertTrue(all(q["change_pct"] == 1.5 for q in quotes))


if __name__ == "__main__":
    unittest.main()
