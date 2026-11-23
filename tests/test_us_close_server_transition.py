"""No-network tests for server-owned last verified US regular-session handoff."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import kiwoom_us_top20_api as api


CAPTURE = dt.datetime(2026, 11, 23, 20, 59, 21, tzinfo=dt.timezone.utc)
HOLD = dt.datetime(2026, 11, 23, 21, 5, 1, tzinfo=dt.timezone.utc)
RESUME = dt.datetime(2026, 11, 23, 21, 30, tzinfo=dt.timezone.utc)


class UsCloseHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.old_cache = api._US_CLOSE_CACHE
        self.old_save = api._US_CLOSE_LAST_SAVE
        self.old_read = api._US_CLOSE_LAST_READ
        self.patches = [
            patch.object(api, "_US_CLOSE_FILE", root / "close.json"),
            patch.object(api, "_US_CLOSE_LOCK_FILE", root / "close.lock"),
            patch.object(api, "_US_CLOSE_LAST_SAVE", 0.0),
            patch.object(api, "_US_CLOSE_LAST_READ", 0.0),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        api._US_CLOSE_CACHE = {"day": "", "items": {}}
        self.addCleanup(lambda: setattr(api, "_US_CLOSE_CACHE", self.old_cache))

    def quote(self, symbol="QQQ", price=650.25, pct=3.21, now=CAPTURE):
        return {
            "symbol": symbol, "exchange": "ND", "price": price,
            "change_pct": pct, "reference_close_date": "2026-11-20",
            "received_at_ms": int(now.timestamp() * 1000), "stale": False
        }

    def test_regular_snapshot_persists_and_new_browser_gets_same_pair(self):
        self.assertEqual(api._us_close_phase(CAPTURE)[0], "capture")
        self.assertTrue(api._us_close_remember(self.quote(), now=CAPTURE))
        self.assertTrue(api._US_CLOSE_FILE.is_file())
        self.assertIsNone(api._us_close_get("QQQ", now=CAPTURE))
        self.assertIsNone(api._us_close_get("QQQ", now=RESUME))
        api._US_CLOSE_CACHE = {"day": "", "items": {}}
        api._US_CLOSE_LAST_READ = 0.0
        val = api._us_close_get("QQQ", now=HOLD)
        self.assertEqual(val["price"], 650.25)
        self.assertEqual(val["change_pct"], 3.21)
        self.assertEqual(val["reference_close_date"], "2026-11-20")
        self.assertEqual(val["market_session"], "last_regular_tick")
        self.assertFalse(val["stale"])
        self.assertEqual(val["received_at_ms"] % 10000, 0)
        self.assertIsNone(api._us_close_get("QQQ", now=RESUME))
        self.assertIsNone(api._us_close_get("QQQ", now=HOLD + dt.timedelta(days=1)))

    def test_rejects_partial_and_after_session_quotes(self):
        self.assertFalse(api._us_close_remember(self.quote(pct=None), now=CAPTURE))
        self.assertFalse(api._us_close_remember(self.quote(price=-10), now=CAPTURE))
        self.assertFalse(api._us_close_remember(self.quote(now=CAPTURE - dt.timedelta(minutes=3)), now=CAPTURE))
        self.assertFalse(api._us_close_remember(self.quote(now=HOLD), now=HOLD))
        self.assertIsNone(api._us_close_get("QQQ", now=HOLD))

    def test_ranking_uses_complete_held_price_and_pct(self):
        self.assertTrue(api._us_close_remember(self.quote("QQQ", 650.25, 3.21), now=CAPTURE))
        rankfile = Path(self.tmp.name) / "top20.json"
        rows = [{
            "rank": i+1, "symbol": f"ZZ{i:02d}", "name": f"Stock {i}",
            "exchange": "ND", "price": 10 + i, "trading_value": 1000 - i,
        } for i in range(20)]
        rows[0]["symbol"] = "QQQ"
        rankfile.write_text(json.dumps({
            "schema_version": 1, "source": "kiwoom", "market": "US",
            "rank_type": "trading_value", "items": rows,
        }), encoding="utf-8")
        original = api._us_close_get
        with patch.object(api, "_us_close_get", side_effect=lambda s: original(s, now=HOLD)), \
             patch("backend.us_quote_change.validated_change", return_value=(None, None)):
            ranking = api.read_top20(rankfile)
        row = ranking["items"][0]
        self.assertEqual(row["price"], 650.25)
        self.assertEqual(row["change_pct"], 3.21)
        self.assertEqual(row["reference_close_date"], "2026-11-20")

    def test_qqq_and_etf_widget_use_held_quote(self):
        self.assertTrue(api._us_close_remember(self.quote(), now=CAPTURE))
        # Simulate an alternate process before seeing the shared file.
        api._US_CLOSE_CACHE = {"day": "", "items": {}}
        api._US_CLOSE_LAST_READ = 0.0
        original = api._us_close_get
        with patch.object(api, "_us_close_get", side_effect=lambda s: original(s, now=HOLD)):
            q = api._qqq_snapshot()
            self.assertEqual(q["price"], 650.25)
            self.assertEqual(q["change_pct"], 3.21)
            self.assertFalse(q["stale"])

    def test_websocket_feed_uses_complete_saved_regular_quote(self):
        self.assertTrue(api._us_close_remember(self.quote(), now=CAPTURE))
        original = api._us_close_get
        current = {
            "symbol": "QQQ", "exchange": "ND", "price": 651.50,
            "change_pct": None, "reference_close_session": "2026-11-23",
            "reference_close_date": None,
            "received_at_ms": int(HOLD.timestamp() * 1000), "stale": False,
        }
        with patch.object(api, "_us_close_get", side_effect=lambda sym: original(sym, now=HOLD)):
            out = api._feed_snapshot({"QQQ": current})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["price"], 650.25)
        self.assertEqual(out[0]["change_pct"], 3.21)
        self.assertFalse(out[0]["stale"])

    def test_spy_dia_do_not_issue_new_rest_reads_when_held(self):
        for sym in ("SPY", "DIA"):
            self.assertTrue(api._us_close_remember(self.quote(sym, 500.0, 1.6), now=CAPTURE))
        original = api._us_close_get
        with patch.object(api, "_us_close_get", side_effect=lambda sym: original(sym, now=HOLD)), \
             patch.object(api, "_market_widget_snapshot", return_value=[]), \
             patch("backend.providers.kiwoom_us_quotes.fetch_us_quote", side_effect=AssertionError("unnecessary REST")):
            rows = api._get_market_widget_quotes()
        self.assertEqual([row["symbol"] for row in rows], ["DIA", "SPY"])
        self.assertTrue(all(row["change_pct"] == 1.6 and row["price"] == 500.0 for row in rows))

    def test_summer_daylight_savings_handoff(self):
        july = dt.datetime(2026, 7, 1, 19, 59, tzinfo=dt.timezone.utc)
        self.assertEqual(api._us_close_phase(july)[0], "capture")
        self.assertEqual(api._us_close_phase(july + dt.timedelta(minutes=2))[0], "hold")
        self.assertEqual(api._us_close_phase(july + dt.timedelta(minutes=31))[0], "none")


if __name__ == "__main__":
    unittest.main()
