import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from backend.providers import kiwoom_us_industries as industries
from backend import kiwoom_us_top20_api as api
from backend.kiwoom_us_live_prices import _industry_only_symbols


class EtfIndustryMapTests(unittest.TestCase):
    def test_heatmap_overlaps_independent_stock_reads_and_keeps_order(self):
        barrier = threading.Barrier(3)
        source = {"items": [{"key": key, "codes": [key]} for key in ("one", "two", "three")]}
        api._US_INDUSTRY_STOCK_CACHE.clear()

        def fetch(codes, sort, *, limit):
            barrier.wait(timeout=2)
            return {"items": [{"name": codes[0], "symbol": codes[0], "market_cap_usd": 1}]}

        with patch.object(api, "_get_us_industry_map", return_value=source), \
             patch.object(industries, "fetch_us_industry_stocks", side_effect=fetch) as calls, \
             patch.object(industries, "fetch_us_bitcoin_related_stocks", return_value=[]), \
             patch.object(api, "_get_us_industry_etf_quotes", return_value=[]):
            result = api._get_us_industry_map_with_stocks("heatmap")
        self.assertEqual([item["key"] for item in result["items"][:3]], ["one", "two", "three"])
        self.assertEqual(calls.call_count, 3)

    def test_same_sector_concurrent_reads_share_one_kiwoom_call(self):
        source = {"items": [{"key": "one", "codes": ["one"]}]}
        api._US_INDUSTRY_STOCK_CACHE.clear()
        entered = threading.Event()
        release = threading.Event()

        def read(_codes, _sort, *, limit):
            entered.set()
            self.assertTrue(release.wait(timeout=2))
            return {"items": [{"symbol": "ONE"}]}

        with patch.object(industries, "fetch_us_industry_stocks", side_effect=read) as calls:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(api._get_us_industry_stocks, "one", sector_map=source)
                self.assertTrue(entered.wait(timeout=2))
                second = pool.submit(api._get_us_industry_stocks, "one", sector_map=source)
                release.set()
                results = [first.result(), second.result()]
        self.assertEqual(calls.call_count, 1)
        self.assertTrue(all(result["items"] for result in results))

    def test_heatmap_overlaps_etf_bitcoin_and_sector_reads(self):
        barrier = threading.Barrier(3)
        source = {"items": [{"key": "one", "codes": ["one"]}]}
        api._US_INDUSTRY_STOCK_CACHE.clear()

        def sector(*_args, **_kwargs):
            barrier.wait(timeout=2)
            return {"items": []}

        def etf():
            barrier.wait(timeout=2)
            return []

        def bitcoin():
            barrier.wait(timeout=2)
            return []

        with patch.object(api, "_get_us_industry_map", return_value=source), \
             patch.object(industries, "fetch_us_industry_stocks", side_effect=sector), \
             patch.object(industries, "fetch_us_bitcoin_related_stocks", side_effect=bitcoin), \
             patch.object(api, "_get_us_industry_etf_quotes", side_effect=etf):
            result = api._get_us_industry_map_with_stocks("heatmap")
        self.assertEqual(result["items"][0]["key"], "one")

    def test_anthropic_requires_verified_kiwoom_ticker_and_market_cap(self):
        record = {"stk_cd": "ANT", "stex_tp": "ND", "mac": "1200000",
                  "cur_prc": "90", "flu_rt": "2.5"}
        with patch.object(industries, "_call", return_value=record) as call:
            stock = industries.fetch_us_anthropic_stock(token="test")
        self.assertEqual((stock["symbol"], stock["change_pct"]), ("ANT", 2.5))
        call.assert_called_once_with("usa20100", {"stex_tp": "ND", "stk_cd": "ANT"}, token="test")
        with patch.object(industries, "_call", return_value={**record, "stk_cd": "OTHER"}):
            self.assertIsNone(industries.fetch_us_anthropic_stock(token="test"))

    def test_share_classes_take_one_market_cap_slot_and_refill_third(self):
        records = [
            {"stk_cd": "GOOG", "stk_nm": "알파벳 Class C", "stk_enm": "Alphabet Inc Class C", "stex_tp": "2", "mac": "900"},
            {"stk_cd": "GOOGL", "stk_nm": "알파벳 Class A", "stk_enm": "Alphabet Inc Class A", "stex_tp": "2", "mac": "850"},
            {"stk_cd": "META", "stk_nm": "메타", "stk_enm": "Meta Platforms", "stex_tp": "2", "mac": "800"},
            {"stk_cd": "NFLX", "stk_nm": "넷플릭스", "stk_enm": "Netflix", "stex_tp": "2", "mac": "700"},
        ]
        with patch.object(industries, "_call", return_value={"result_list": records}):
            rows = industries.fetch_us_industry_stocks("370", token="test", limit=3)["items"]
        self.assertEqual([row["symbol"] for row in rows], ["GOOG", "META", "NFLX"])
        self.assertEqual([row["rank"] for row in rows], [1, 2, 3])
        self.assertEqual(industries._issuer_key("BRK.A", "Berkshire Hathaway A", ""),
                         industries._issuer_key("BRK.B", "Berkshire Hathaway B", ""))

    def test_shared_market_quotes_are_subscribed_once(self):
        self.assertEqual(_industry_only_symbols(
            {"QQQ": "ND", "NVDA": "ND", "XLU": "NA", "COIN": "ND"},
            {"NVDA": "ND", "COIN": "ND"}), {"XLU": "NA"})

    def test_six_sector_code_matches_use_kiwoom_names(self):
        official = [
            {"inds_cd": "910", "inds_nm": "전기", "inds_enm": "Electric Utilities"},
            {"inds_cd": "630", "inds_nm": "부동산", "inds_enm": "Real Estate"},
            {"inds_cd": "110", "inds_nm": "화학", "inds_enm": "Chemicals"},
            {"inds_cd": "710", "inds_nm": "반도체", "inds_enm": "Semiconductors"},
            {"inds_cd": "530", "inds_nm": "바이오", "inds_enm": "Biotechnology"},
        ]
        result = industries._build_us_industry_map(official, [], industries.INDUSTRY_GROUPS)
        by_key = {row["key"]: row["codes"] for row in result["items"]}
        self.assertEqual({key: by_key[key] for key in
                          ("utilities", "real_estate", "materials", "semiconductors", "biotech")},
                         {"utilities": ["910"], "real_estate": ["630"], "materials": ["110"],
                          "semiconductors": ["710"], "biotech": ["530"]})

    def test_etf_exchange_comes_from_official_list(self):
        expected = {
            "IBIT": "ND", "SOXX": "ND", "XBI": "NY", "XLB": "NY",
            "XLC": "NY", "XLE": "NY", "XLF": "NY", "XLI": "NY",
            "XLK": "NY", "XLP": "NY", "XLRE": "NY", "XLU": "NY",
            "XLV": "NY", "XLY": "NY", "SPY": "NY", "DIA": "NY",
        }
        records = [
            {"stk_cd": symbol, "stex_tp": exchange, "etn": "N"}
            for symbol, exchange in expected.items()
        ]
        records.extend([
            {"stk_cd": "SOMEETN", "stex_tp": "NY", "etn": "Y"},
            # The obsolete field must not be treated as a Kiwoom ticker.
            {"code": "XLV", "stex_tp": "ND", "etn": "N"},
        ])
        with patch.object(industries, "_call", return_value={"list": records}) as call:
            actual = industries.fetch_us_etf_exchanges(token="test")
        self.assertEqual(actual, {symbol: exchange for symbol, exchange in expected.items()
                                  if symbol in industries.ETF_TICKERS})
        self.assertEqual(len(actual), 14)
        self.assertEqual(set(actual), set(industries.ETF_TICKERS))
        call.assert_called_once_with("usa10104", {"stex_tp": "%"}, token="test")
        with patch.object(industries, "_call", return_value={"list": records}):
            widgets = industries.fetch_us_etf_exchanges(token="test", tickers={"SPY", "DIA"})
        self.assertEqual(widgets, {"SPY": "NY", "DIA": "NY"})

    def test_map_and_widget_quotes_are_requested_separately(self):
        api._US_INDUSTRY_ETF_CACHE.clear()

        def quotes(*, symbols):
            return [{"symbol": symbol, "price": 100, "change_pct": 1,
                     "received_at_ms": 1763850000000} for symbol in symbols]

        with patch.object(industries, "fetch_us_etf_quotes", side_effect=quotes) as fetch:
            industry = api._get_us_industry_etf_quotes()
            widgets = api._get_us_industry_etf_quotes(symbols={"SPY", "DIA"})
        self.assertEqual({row["symbol"] for row in industry}, industries.ETF_TICKERS)
        self.assertEqual({row["symbol"] for row in widgets}, {"SPY", "DIA"})
        self.assertEqual(fetch.call_count, 2)

    def test_missing_etf_quotes_overlap_without_extra_calls(self):
        symbols = ("DIA", "SPY", "XLK")
        barrier = threading.Barrier(len(symbols))

        def quote(symbol, exchange, *, token):
            barrier.wait(timeout=2)
            return {"current": "100", "change_pct": "1"}

        with patch.object(industries, "ETF_TICKERS", frozenset(symbols)), \
             patch.object(industries, "fetch_us_etf_marketcap", return_value={"items": []}), \
             patch.object(industries, "fetch_us_etf_exchanges", return_value=dict.fromkeys(symbols, "NY")), \
             patch.object(industries, "fetch_us_quote", side_effect=quote) as calls:
            rows = industries.fetch_us_etf_quotes(token="test")
        self.assertEqual([row["symbol"] for row in rows], list(symbols))
        self.assertEqual(calls.call_count, len(symbols))

    def test_bitcoin_related_companies_are_ranked_by_market_cap(self):
        caps = {"COIN": 10, "MSTR": 50, "MARA": 5, "RIOT": 20, "CLSK": 1}

        def response(api, body, *, token):
            self.assertEqual(api, "usa20100")
            symbol = body["stk_cd"]
            return {"stk_cd": symbol, "stex_tp": "ND", "stk_nm": symbol,
                    "mac": str(caps[symbol]), "cur_prc": "20", "flu_rt": "1"}

        with patch.object(industries, "_call", side_effect=response):
            rows = industries.fetch_us_bitcoin_related_stocks(token="test")
        self.assertEqual([row["symbol"] for row in rows], ["MSTR", "RIOT", "COIN"])


if __name__ == "__main__":
    unittest.main()
