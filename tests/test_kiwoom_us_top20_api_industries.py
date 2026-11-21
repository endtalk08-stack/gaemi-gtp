"""No-network tests for the in-memory US industry quote integration."""
import asyncio
import json
import sys
import threading
import unittest
from types import ModuleType
from unittest.mock import patch

from backend import kiwoom_us_live_prices as live
from backend import kiwoom_us_top20_api as api
from backend.providers import kiwoom_us_industries, kiwoom_us_quotes


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
                {"symbol": "AMD", "exchange": "ND"},
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
                "NVDA": "ND", "AVGO": "ND", "AMD": "ND", "WMT": "NY"
            })

    def test_incomplete_heatmap_keeps_existing_industry_keys_and_stocks(self):
        legacy = {"ok": True, "items": [{"key": "defense", "codes": ["210"]}]}
        heatmap = {"items": [
            {"key": "industrials", "mapping_status": "matched"},
            {"key": "internet_platforms", "mapping_status": "unmatched"},
        ]}
        stocks = [{"symbol": "LMT"}, {"symbol": "BA"}, {"symbol": "RTX"}]
        with (
            patch.object(api, "_get_us_industry_maps", return_value={"legacy": legacy, "heatmap": heatmap}),
            patch.object(api, "_get_us_industry_stocks", return_value={"items": stocks}) as fetch,
            patch.object(api, "_get_us_internet_platform_group", return_value=None) as platform,
        ):
            default = api._get_us_industry_map_with_stocks()
            platform.assert_not_called()
            requested = api._get_us_industry_map_with_stocks("heatmap")

        platform.assert_called_once_with()
        self.assertNotIn("heatmap_ready", default)
        self.assertEqual(default["items"][0]["stocks"], stocks)
        self.assertFalse(requested["heatmap_ready"])
        self.assertEqual(requested["heatmap_missing"], ["internet_platforms"])
        self.assertEqual(requested["view"], "legacy")
        self.assertEqual(requested["items"], default["items"])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(fetch.call_args.args, ("defense", "marketcap"))

    def test_ready_heatmap_keeps_three_market_cap_leaders(self):
        sector = {"key": "energy", "codes": ["10"], "mapping_status": "matched"}
        stocks = [{"symbol": symbol} for symbol in ("AAA", "BBB", "CCC", "DDD")]
        with patch.object(api, "_get_us_industry_maps", return_value={
            "legacy": {"items": []}, "heatmap": {"items": [sector]},
        }), patch.object(api, "_get_us_industry_stocks", return_value={"items": stocks}) as fetch:
            result = api._get_us_industry_map_with_stocks("heatmap")

        self.assertTrue(result["heatmap_ready"])
        self.assertEqual(result["view"], "heatmap")
        self.assertEqual(result["items"][0]["stocks"], stocks[:3])
        fetch.assert_called_once_with("energy", "marketcap", sector_map={
            "items": [sector], "view": "heatmap", "heatmap_ready": True, "heatmap_missing": [],
        })

    def test_representative_platform_completes_heatmap_and_reuses_its_ranked_stocks(self):
        items = [
            {"key": key, "name": name, "change_pct": -1.0, "mapping_status": "matched"}
            for key, name, _ in kiwoom_us_industries.INDUSTRY_GROUPS
        ]
        platform = next(item for item in items if item["key"] == "internet_platforms")
        platform.update(change_pct=None, mapping_status="unmatched")
        leaders = [{"symbol": symbol, "exchange": "ND"} for symbol in ("GOOG", "META", "NFLX")]
        representative = {"change_pct": 1.5, "mapping_status": "matched", "stocks": leaders}
        with (
            patch.object(api, "_get_us_industry_maps", return_value={
                "legacy": {"items": []}, "heatmap": {"items": items, "mapping_complete": False},
            }),
            patch.object(api, "_get_us_internet_platform_group", return_value=representative),
            patch.object(api, "_get_us_industry_stocks") as fetch,
        ):
            result = api._get_us_industry_map_with_stocks("heatmap")

        self.assertTrue(result["heatmap_ready"])
        self.assertTrue(result["mapping_complete"])
        self.assertEqual(len(result["items"]), 11)
        self.assertEqual(result["items"][0]["key"], "internet_platforms")
        self.assertEqual(result["items"][0]["rank"], 1)
        self.assertEqual(result["items"][0]["stocks"], leaders)
        self.assertEqual(platform["mapping_status"], "unmatched")
        fetch.assert_not_called()

    def test_platform_lookup_reuses_the_sixty_second_cache_even_when_incomplete(self):
        with (
            patch.dict(api._US_PLATFORM_CACHE, {"expires_at": 0.0, "data": None}),
            patch.object(kiwoom_us_industries, "fetch_us_internet_platform_group", return_value=None) as fetch,
            patch.object(api.time, "monotonic", side_effect=[100, 100, 159, 160, 160]),
        ):
            self.assertIsNone(api._get_us_internet_platform_group())
            self.assertIsNone(api._get_us_internet_platform_group())
            self.assertEqual(fetch.call_count, 1)
            self.assertIsNone(api._get_us_internet_platform_group())
            self.assertEqual(fetch.call_count, 2)

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


class KiwoomUSIndustryStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_qqq_and_top20_ticks_continue_while_industry_lookup_is_pending(self):
        loop = asyncio.get_running_loop()
        lookup_started = asyncio.Event()
        release_lookup = threading.Event()
        existing_ticks = asyncio.Event()
        group_three_registered = asyncio.Event()
        updates = {}
        sent = []
        frames = asyncio.Queue()

        def fetch_industry():
            loop.call_soon_threadsafe(lookup_started.set)
            if not release_lookup.wait(timeout=4):
                raise TimeoutError("test lookup was not released")
            return {"TSM": "NY", "BAD\\NAME": "NY"}

        def on_quote(quote):
            updates[quote["symbol"]] = quote["price"]
            if {"QQQ", "NVDA"} <= updates.keys():
                existing_ticks.set()

        class Feed:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return None

            async def recv(self):
                return await frames.get()

            async def send(self, value):
                message = json.loads(value)
                sent.append(message)
                kind = message["trnm"]
                if kind in ("LOGIN", "REG"):
                    frames.put_nowait(json.dumps({"trnm": kind, "return_code": 0}))

        mock_client = ModuleType("websockets.asyncio.client")
        mock_client.connect = lambda *args, **kwargs: Feed()

        with (
            patch.dict(sys.modules, {"websockets.asyncio.client": mock_client}),
            patch.object(kiwoom_us_quotes, "issue_access_token", return_value="LOCAL_TEST"),
            patch.object(live, "_open_us_session", return_value=True),
            patch.object(live, "_ranked_symbols", return_value=(None, {"NVDA": "ND"})),
        ):
            task = asyncio.create_task(live.run_qqq_fe_stream(
                on_quote,
                on_top20=lambda _: None,
                on_industry=lambda _: group_three_registered.set(),
                get_industry_symbols=fetch_industry,
            ))
            try:
                await asyncio.wait_for(lookup_started.wait(), timeout=1)
                frames.put_nowait(json.dumps({
                    "trnm": "REAL",
                    "data": [
                        {"type": "FE", "item": "QQQ", "values": {"10": "500"}},
                        {"type": "FE", "item": "NVDA", "values": {"10": "150"}},
                    ],
                }))
                await asyncio.wait_for(existing_ticks.wait(), timeout=1)
                self.assertEqual(updates, {"QQQ": 500, "NVDA": 150})
                self.assertFalse(group_three_registered.is_set())
                release_lookup.set()

                async def wake_reader():
                    while not group_three_registered.is_set():
                        frames.put_nowait(json.dumps({"trnm": "PING"}))
                        await asyncio.sleep(0.01)

                await asyncio.wait_for(wake_reader(), timeout=1)
                groups = [message for message in sent if message["trnm"] == "REG"]
                self.assertEqual([message["grp_no"] for message in groups], ["1", "2", "3"])
                self.assertEqual(groups[-1]["data"][0]["item"], [{"jmcode": "TSM", "stex_tp": "NY"}])
            finally:
                release_lookup.set()
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

if __name__ == "__main__":
    unittest.main()
