"""No-network tests for the in-memory US industry quote integration."""
import unittest
from unittest.mock import patch

from backend import kiwoom_us_top20_api as api


class KiwoomUSIndustryLiveApiTests(unittest.TestCase):
    def setUp(self):
        api._TOP20_SYMBOLS = frozenset()
        api._INDUSTRY_SYMBOLS = frozenset()
        api._TOP20_QUOTES.clear()
        api._INDUSTRY_QUOTES.clear()
        api._QQQ_QUOTE = None

    def test_industry_symbol_list_is_deduplicated_and_exchange_validated(self):
        source = {"items": [
            {"stocks": [
                {"symbol": "NVDA", "exchange": "ND"},
                {"symbol": "AVGO", "exchange": "ND"},
            ]},
            {"stocks": [
                {"symbol": "NVDA", "exchange": "ND"},
                {"symbol": "WMT", "exchange": "NY"},
                {"symbol": "../BAD", "exchange": "ND"},
                {"symbol": "BAD", "exchange": "OTC"},
            ]},
        ]}
        with patch.object(api, "_get_us_industry_map_with_stocks", return_value=source):
            self.assertEqual(api.get_us_industry_symbols(), {
                "NVDA": "ND", "AVGO": "ND", "WMT": "NY"
            })

    def test_incomplete_heatmap_keeps_existing_industry_keys_and_stocks(self):
        legacy = {"ok": True, "items": [{"key": "defense", "codes": ["210"]}]}
        heatmap = {"items": [
            {"key": "industrials", "mapping_status": "matched"},
            {"key": "internet_platforms", "mapping_status": "unmatched"},
        ]}
        stocks = [{"symbol": "LMT"}, {"symbol": "BA"}, {"symbol": "RTX"}]
        with patch.object(api, "_get_us_industry_maps", return_value={
            "legacy": legacy, "heatmap": heatmap,
        }), patch.object(api, "_get_us_industry_stocks", return_value={"items": stocks}) as fetch:
            default = api._get_us_industry_map_with_stocks()
            requested = api._get_us_industry_map_with_stocks("heatmap")

        self.assertNotIn("heatmap_ready", default)
        self.assertEqual(default["items"][0]["stocks"], stocks)
        self.assertFalse(requested["heatmap_ready"])
        self.assertEqual(requested["heatmap_missing"], ["internet_platforms"])
        self.assertEqual(requested["view"], "legacy")
        self.assertEqual(requested["items"], default["items"])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(fetch.call_args.args, ("defense", "marketcap"))

    def test_ready_heatmap_keeps_only_two_market_cap_leaders(self):
        sector = {"key": "energy", "codes": ["10"], "mapping_status": "matched"}
        stocks = [{"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": "CCC"}]
        with patch.object(api, "_get_us_industry_maps", return_value={
            "legacy": {"items": []}, "heatmap": {"items": [sector]},
        }), patch.object(api, "_get_us_industry_stocks", return_value={"items": stocks}) as fetch:
            result = api._get_us_industry_map_with_stocks("heatmap")

        self.assertTrue(result["heatmap_ready"])
        self.assertEqual(result["view"], "heatmap")
        self.assertEqual(result["items"][0]["stocks"], stocks[:2])
        fetch.assert_called_once_with("energy", "marketcap", sector_map={
            "items": [sector], "view": "heatmap", "heatmap_ready": True, "heatmap_missing": [],
        })

    def test_top20_and_industry_quote_snapshots_keep_separate_payloads(self):
        api._TOP20_SYMBOLS = frozenset({"AAA"})
        api._INDUSTRY_SYMBOLS = frozenset({"AAA", "BBB"})
        top20 = {
            "symbol": "AAA", "price": 10.0, "change_pct": 1.0,
            "received_at_ms": 1000, "stale": False,
        }
        industry = {
            "symbol": "BBB", "price": 20.0, "change_pct": -1.0,
            "received_at_ms": 1000, "stale": False,
        }
        api._TOP20_QUOTES["AAA"] = top20
        api._INDUSTRY_QUOTES["AAA"] = top20
        api._INDUSTRY_QUOTES["BBB"] = industry
        self.assertEqual([row["symbol"] for row in api._top20_snapshot()], ["AAA"])
        self.assertEqual({row["symbol"] for row in api._industry_snapshot()}, {"AAA", "BBB"})


if __name__ == "__main__":
    unittest.main()
