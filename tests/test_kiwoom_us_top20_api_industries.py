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

    def test_industry_map_keeps_only_two_market_cap_leaders_per_group(self):
        stocks = [
            {"symbol": "AAA", "name": "A"},
            {"symbol": "BBB", "name": "B"},
            {"symbol": "CCC", "name": "C"},
        ]
        with patch.object(api, "_get_us_industry_map", return_value={
            "ok": True, "items": [{"key": "energy", "codes": ["001"]}]
        }), patch.object(api, "_get_us_industry_stocks", return_value={
            "items": stocks
        }) as fetch:
            result = api._get_us_industry_map_with_stocks()
        fetch.assert_called_once_with("energy", "marketcap")
        self.assertEqual(result["items"][0]["stocks"], stocks[:2])

    def test_live_quote_snapshot_combines_top20_and_industry_without_duplicates(self):
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
        rows = api._top20_snapshot()
        self.assertEqual({row["symbol"] for row in rows}, {"AAA", "BBB"})
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
