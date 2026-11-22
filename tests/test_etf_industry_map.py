import unittest
from unittest.mock import patch

from backend.providers import kiwoom_us_industries as industries
from backend.kiwoom_us_live_prices import _industry_only_symbols


class EtfIndustryMapTests(unittest.TestCase):
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
            "XLV": "NY", "XLY": "NY",
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
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 14)
        self.assertEqual(set(actual), set(industries.ETF_TICKERS))
        call.assert_called_once_with("usa10104", {"stex_tp": "%"}, token="test")

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
