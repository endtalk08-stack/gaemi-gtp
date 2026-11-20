"""No-network tests for Kiwoom's official US industry and ETF APIs."""
import unittest
from unittest.mock import patch

from backend.providers import kiwoom_us_industries as sectors


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class KiwoomUSIndustryTests(unittest.TestCase):
    def setUp(self):
        sectors._ACCESS_TOKEN = None
        sectors._ACCESS_TOKEN_EXPIRES_AT = 0

    def test_sector_map_uses_eleven_display_groups_and_official_codes(self):
        names = [
            ("에너지", "Energy"),
            ("금융", "Financials"),
            ("필수소비재", "Consumer Staples"),
            ("산업재", "Industrials"),
            ("인터넷 플랫폼", "Internet Platforms"),
            ("소프트웨어", "Software"),
            ("커뮤니케이션", "Communication Services"),
            ("헬스케어", "Health Care Equipment & Services"),
            ("경기소비재", "Consumer Discretionary"),
            ("IT 하드웨어", "Technology Hardware & Equipment"),
            ("반도체", "Semiconductors & Semiconductor Equipment"),
        ]
        official = [
            {"inds_cd": str(index).zfill(3), "inds_nm": name, "inds_enm": english}
            for index, (name, english) in enumerate(names, 1)
        ]
        performance = [
            {"inds_cd": str(index).zfill(3), "perf_1d": str(index), "perf_5d": "1.25", "perf_1m": "2.50"}
            for index in range(1, 12)
        ]
        sent = []

        def post(url, **kwargs):
            sent.append((url, kwargs))
            payload = {"return_code": 0, "list": official} if len(sent) == 1 else {
                "return_code": 0, "result_list": performance
            }
            return FakeResponse(payload)

        with patch.object(sectors, "issue_access_token", return_value="MOCK_TOKEN"), \
             patch.object(sectors.requests, "post", side_effect=post):
            result = sectors.fetch_us_industry_map()

        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0][1]["headers"]["api-id"], "usa10101")
        self.assertEqual(sent[0][1]["json"], {"gubun": "1"})
        self.assertEqual(sent[1][1]["headers"]["api-id"], "usa23000")
        self.assertEqual(len(result["items"]), 11)
        self.assertTrue(result["mapping_complete"])
        self.assertEqual({item["key"] for item in result["items"]}, {
            "energy", "finance", "consumer_staples", "industrials",
            "internet_platforms", "software", "communication", "healthcare",
            "consumer_discretionary", "it_hardware", "semiconductors",
        })
        self.assertEqual(next(item for item in result["items"] if item["key"] == "semiconductors")["change_pct"], 11.0)

    def test_official_names_map_to_the_eleven_heatmap_groups(self):
        expected = (
            ("Energy", "energy"),
            ("Banks", "finance"),
            ("Consumer Staples", "consumer_staples"),
            ("Industrials", "industrials"),
            ("Internet Software & Services", "internet_platforms"),
            ("Software", "software"),
            ("Communication Services", "communication"),
            ("Health Care Equipment & Services", "healthcare"),
            ("Automobiles & Components", "consumer_discretionary"),
            ("Technology Hardware & Equipment", "it_hardware"),
            ("Semiconductors & Semiconductor Equipment", "semiconductors"),
        )
        for official_name, expected_group in expected:
            with self.subTest(official_name=official_name):
                self.assertEqual(
                    sectors._group_for_official_industry(official_name),
                    expected_group,
                )

    def test_unrelated_official_names_are_not_guessed(self):
        self.assertIsNone(sectors._group_for_official_industry("Utilities", "Utilities"))
        self.assertIsNone(sectors._group_for_official_industry("Real Estate", "Real Estate"))
        self.assertEqual(
            sectors._group_for_official_industry("Interactive Media & Services"),
            "internet_platforms",
        )

    def test_multiple_official_codes_are_combined_without_guessing(self):
        official = [
            {"inds_cd": "001", "inds_nm": "은행", "inds_enm": "Banks"},
            {"inds_cd": "002", "inds_nm": "보험", "inds_enm": "Insurance"},
        ]
        performance = [
            {"inds_cd": "001", "perf_1d": "1.0", "perf_5d": "2.0", "perf_1m": "3.0"},
            {"inds_cd": "002", "perf_1d": "3.0", "perf_5d": "4.0", "perf_1m": "5.0"},
        ]
        with patch.object(sectors, "issue_access_token", return_value="MOCK_TOKEN"), \
             patch.object(sectors.requests, "post", side_effect=[
                 FakeResponse({"return_code": 0, "list": official}),
                 FakeResponse({"return_code": 0, "result_list": performance}),
             ]):
            result = sectors.fetch_us_industry_map()
        finance = next(item for item in result["items"] if item["key"] == "finance")
        self.assertEqual(finance["codes"], ["001", "002"])
        self.assertEqual(finance["change_pct"], 2.0)
        self.assertEqual(finance["change_method"], "equal_weighted_official_industry_returns")
        self.assertEqual(finance["mapping_status"], "matched")

    def test_change_sort_uses_usa23100_for_selected_industry(self):
        sent = []

        def post(url, **kwargs):
            sent.append((url, kwargs))
            return FakeResponse({"return_code": 0, "result_list": [
                {"stk_cd": "AAA", "stk_nm": "A Company", "stex_tp": "ND",
                 "cur_prc": "10.25", "flu_rt": "2.10", "acc_trde_qty": "1000"},
                {"stk_cd": "BBB", "stk_nm": "B Company", "stex_tp": "NY",
                 "cur_prc": "-20.50", "flu_rt": "5.20", "acc_trde_qty": "2000"},
            ]})

        with patch.object(sectors, "issue_access_token", return_value="MOCK_TOKEN"), \
             patch.object(sectors.requests, "post", side_effect=post):
            result = sectors.fetch_us_industry_stocks("001", "change")

        self.assertEqual(sent[0][1]["headers"]["api-id"], "usa23100")
        self.assertEqual(sent[0][1]["json"], {
            "stex_tp": "0", "sort_tp": "1", "inds_cd": "001"
        })
        self.assertEqual(result["items"][0]["symbol"], "BBB")
        self.assertEqual(result["items"][0]["price"], 20.50)

    def test_value_sort_uses_usa20540(self):
        sent = []

        def post(url, **kwargs):
            sent.append((url, kwargs))
            return FakeResponse({"return_code": 0, "result_list": [
                {"stk_cd": "AAA", "stk_nm": "A Company", "stex_tp": "ND",
                 "cur_prc": "10", "flu_rt": "1.5", "acc_trde_qty": "500",
                 "trde_prica": "1234.5"},
            ]})

        with patch.object(sectors, "issue_access_token", return_value="MOCK_TOKEN"), \
             patch.object(sectors.requests, "post", side_effect=post):
            result = sectors.fetch_us_industry_stocks("001", "value")

        self.assertEqual(sent[0][1]["headers"]["api-id"], "usa20540")
        self.assertEqual(result["items"][0]["trading_value"], 1234500.0)

    def test_marketcap_sort_uses_usa20550_and_orders_by_market_cap(self):
        sent = []

        def post(url, **kwargs):
            sent.append((url, kwargs))
            code = kwargs["json"]["inds_cd"]
            records = {
                "001": [
                    {"stk_cd": "NOCAP", "stk_nm": "시가총액 누락", "stex_tp": "ND",
                     "cur_prc": "300", "flu_rt": "9.0", "rank": "1"},
                    {"stk_cd": "NVDA", "stk_nm": "엔비디아", "stex_tp": "ND",
                     "cur_prc": "100", "flu_rt": "1.5", "mac": "1000", "rank": "2"},
                    {"stk_cd": "AVGO", "stk_nm": "브로드컴", "stex_tp": "ND",
                     "cur_prc": "200", "flu_rt": "2.5", "mac": "1200", "rank": "1"},
                ],
                "002": [
                    {"stk_cd": "AMD", "stk_nm": "AMD", "stex_tp": "ND",
                     "cur_prc": "150", "flu_rt": "-1.5", "mac": "900", "rank": "3"},
                ],
            }[code]
            return FakeResponse({"return_code": 0, "result_list": records})

        with patch.object(sectors, "issue_access_token", return_value="MOCK_TOKEN"), \
             patch.object(sectors.requests, "post", side_effect=post):
            result = sectors.fetch_us_industry_stocks(["001", "002"], "marketcap", limit=3)

        self.assertEqual(len(sent), 2)
        self.assertTrue(all(item[1]["headers"]["api-id"] == "usa20550" for item in sent))
        self.assertEqual(result["items"][0]["symbol"], "AVGO")
        self.assertEqual(result["items"][0]["market_cap_usd"], 1200000.0)
        self.assertEqual(result["items"][1]["symbol"], "NVDA")

    def test_default_sort_is_marketcap(self):
        with patch.object(sectors, "issue_access_token", return_value="MOCK_TOKEN"), \
             patch.object(sectors.requests, "post", return_value=FakeResponse({"return_code": 0, "result_list": [
                 {"stk_cd": "NVDA", "stk_nm": "엔비디아", "stex_tp": "ND",
                  "cur_prc": "10", "flu_rt": "1.5", "mac": "1000", "rank": "1"},
             ]})) as post:
            result = sectors.fetch_us_industry_stocks("001")
        self.assertEqual(result["sort"], "marketcap")
        self.assertEqual(post.call_args.kwargs["headers"]["api-id"], "usa20550")

    def test_etf_marketcap_uses_usa20551(self):
        with patch.object(sectors, "issue_access_token", return_value="MOCK_TOKEN"), \
             patch.object(sectors.requests, "post", return_value=FakeResponse({"return_code": 0, "result_list": [
                 {"stk_cd": "VOO", "stk_nm": "S&P 500 뱅가드 ETF", "stex_tp": "NY",
                  "cur_prc": "600", "flu_rt": "0.44", "mac": "992777015", "rank": "1"},
             ]})) as post:
            result = sectors.fetch_us_etf_marketcap()
        self.assertEqual(post.call_args.kwargs["headers"]["api-id"], "usa20551")
        self.assertEqual(post.call_args.kwargs["json"]["etf_cat1"], "")
        self.assertEqual(result["items"][0]["symbol"], "VOO")
        self.assertEqual(result["items"][0]["market_cap_usd"], 992777015000.0)

    def test_invalid_code_and_sort_are_rejected_before_network(self):
        with patch.object(sectors.requests, "post", side_effect=AssertionError("network not allowed")):
            with self.assertRaises(ValueError):
                sectors.fetch_us_industry_stocks("../bad", "change", token="MOCK_TOKEN")
            with self.assertRaises(ValueError):
                sectors.fetch_us_industry_stocks("001", "price", token="MOCK_TOKEN")


if __name__ == "__main__":
    unittest.main()
