"""No-network tests for isolated Kiwoom US market read-only adapter."""
import datetime as dt
import json
import os
import unittest
from unittest.mock import patch

from backend.providers import kiwoom_us_quotes as kiwoom


class FakeReply:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class KiwoomReadOnlyTests(unittest.TestCase):
    def test_oauth_request(self):
        seen = []

        def send(req, timeout):
            seen.append((req.full_url, json.loads(req.data)))
            return FakeReply({"return_code": 0, "token": "MOCK_TOKEN"})

        with patch.dict(os.environ, {
            "GAEMI_KIWOOM_APP_KEY": "TEST_KEY",
            "GAEMI_KIWOOM_APP_SECRET": "TEST_SECRET",
        }), patch.object(kiwoom.urllib.request, "urlopen", side_effect=send):
            self.assertEqual(kiwoom.issue_access_token(), "MOCK_TOKEN")
        self.assertEqual(seen, [(
            "https://api.kiwoom.com/oauth2/token",
            {"grant_type": "client_credentials", "appkey": "TEST_KEY",
             "secretkey": "TEST_SECRET"},
        )])

    def test_daily_uses_exact_close(self):
        def send(req, timeout):
            self.assertEqual(req.get_header("Api-id"), "usa20590")
            self.assertEqual(req.get_header("Authorization"), "Bearer MOCK_TOKEN")
            self.assertEqual(json.loads(req.data)["base_dt"], "20261019")
            return FakeReply({"return_code": 0, "result_list": [
                {"dt": "20261016", "cur_prc": "100", "flu_rt": "1.10"},
                {"dt": "20261019", "cur_prc": "124.25",
                 "flu_rt": "-2.15", "acc_trde_qty": "5,500"},
            ]})

        with patch.object(kiwoom.urllib.request, "urlopen", side_effect=send):
            answer = kiwoom.fetch_us_close(
                "nvda", "nd", dt.date(2026, 10, 19), token="MOCK_TOKEN")
        self.assertEqual(answer["session_date"], "2026-10-19")
        self.assertEqual(answer["close"], 124.25)
        self.assertEqual(answer["change_pct"], -2.15)
        self.assertEqual(answer["volume"], 5500)

    def test_no_stale_price(self):
        with patch.object(kiwoom.urllib.request, "urlopen",
                          return_value=FakeReply({"return_code": 0, "result_list": [
                              {"dt": "20261016", "cur_prc": "100", "flu_rt": "1"}
                          ]})):
            self.assertIsNone(kiwoom.fetch_us_close(
                "AAPL", "ND", dt.date(2026, 10, 19), token="MOCK_TOKEN"))

    def test_orders_rejected(self):
        with self.assertRaises(kiwoom.KiwoomReadOnlyError):
            kiwoom._market_request("ust20000", {}, "MOCK_TOKEN")

    def test_invalid_symbol(self):
        with self.assertRaises(ValueError):
            kiwoom.fetch_us_close(
                "../../bad", "ND", dt.date(2026, 10, 19), token="MOCK_TOKEN")

    def test_missing_credentials(self):
        with patch.dict(os.environ, {"GAEMI_KIWOOM_APP_KEY": "",
                                     "GAEMI_KIWOOM_APP_SECRET": ""}):
            with self.assertRaises(kiwoom.KiwoomReadOnlyError):
                kiwoom.issue_access_token()


if __name__ == "__main__":
    unittest.main()
