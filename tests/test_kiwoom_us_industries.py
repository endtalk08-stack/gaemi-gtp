"""No-network tests for Kiwoom's official US industry APIs."""
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

    def test_sector_map_uses_official_list_and_period_returns(self):
        names = [
            ("에너지", "Energy"),
            ("금융", "Financials"),
            ("필수소비재", "Consumer Staples"),
            ("산업재", "Industrials"),
            ("인터넷플랫폼", "Internet Platforms"),
            ("소프트웨어", "Software"),
            ("커뮤니케이션", "Communication Services"),
            ("헬스케어", "Healthcare"),
            ("경기소비재", "Consumer Discretionary"),
            ("IT하드웨어", "IT Hardware"),
            ("반도체", "Semiconductors"),
        ]
        official = [
            {"inds_cd": str(index).zfill(3), "inds_nm": name, "inds_enm": english}
            for index, (name, english) in enumerate(names, 1)
        ]
        performance = [
            {"inds_cd": str(index).zfill(3), "inds_nm": name, "perf_1d": str(index - 6),
             "perf_5d": "1.25", "perf_1m": "2.50"}
            for index, (name, _english) in enumerate(names, 1)
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
        self.assertEqual(sent[0][0], "https://api.kiwoom.com/api/us/stkinfo")
        self.assertEqual(sent[0][1]["headers"]["api-id"], "usa10101")
        self.assertEqual(sent[0][1]["json"], {"gubun": "1"})
        self.assertEqual(sent[1][0], "https://api.kiwoom.com/api/us/sect")
        self.assertEqual(sent[1][1]["headers"]["api-id"], "usa23000")
        self.assertEqual(sent[1][1]["json"], {"stex_tp": "0", "inds_cd": "0"})
        self.assertTrue(result["mapping_complete"])
        self.assertEqual(len(result["items"]), 11)
        self.assertEqual(result["items"][0]["name"], "반도체")
        self.assertEqual(result["items"][0]["change_pct"], 5.0)

    def test_missing_or_ambiguous_official_mapping_is_not_guessed(self):
        official = [
            {"inds_cd": "001", "inds_nm": "금융", "inds_enm": "Financials"},
            {"inds_cd": "002", "inds_nm": "금융", "inds_enm": "Financial Services"},
        ]
        with patch.object(sectors, "issue_access_token", return_value="MOCK_TOKEN"), \
             patch.object(sectors.requests, "post", side_effect=[
                 FakeResponse({"return_code": 0, "list": official}),
                 FakeResponse({"return_code": 0, "result_list": []}),
             ]):
            result = sectors.fetch_us_industry_map()
        finance = next(item for item in result["items"] if item["key"] == "finance")
        self.assertIsNone(finance["code"])
        self.assertEqual(finance["mapping_status"], "ambiguous")
        self.assertFalse(result["mapping_complete"])

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

        self.assertEqual(sent[0][0], "https://api.kiwoom.com/api/us/sect")
        self.assertEqual(sent[0][1]["headers"]["api-id"], "usa23100")
        self.assertEqual(sent[0][1]["json"], {
            "stex_tp": "0", "sort_tp": "1", "inds_cd": "001"
        })
        self.assertEqual(result["items"][0]["symbol"], "BBB")
        self.assertEqual(result["items"][0]["price"], 20.50)

    def test_value_sort_uses_usa20540_and_converts_thousand_usd(self):
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

        self.assertEqual(sent[0][0], "https://api.kiwoom.com/api/us/rkinfo")
        self.assertEqual(sent[0][1]["headers"]["api-id"], "usa20540")
        self.assertEqual(sent[0][1]["json"]["inds_cd"], "001")
        self.assertEqual(result["items"][0]["trading_value"], 1234500.0)

    def test_invalid_code_and_sort_are_rejected_before_network(self):
        with patch.object(sectors.requests, "post", side_effect=AssertionError("network not allowed")):
            with self.assertRaises(ValueError):
                sectors.fetch_us_industry_stocks("../bad", "change", token="MOCK_TOKEN")
            with self.assertRaises(ValueError):
                sectors.fetch_us_industry_stocks("001", "price", token="MOCK_TOKEN")


if __name__ == "__main__":
    unittest.main()
