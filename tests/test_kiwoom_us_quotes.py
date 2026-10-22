"""No-network regressions for the official-style Kiwoom read-only REST adapter."""
import datetime as dt
import os
import unittest
from unittest.mock import patch

import requests

from backend.providers import kiwoom_us_quotes as kiwoom


class FakeResponse:
    def __init__(self, payload=None, status_code=200, headers=None, content=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}
        self.content = content if content is not None else b'{"return_code":0}'

    def json(self):
        if self.payload is None:
            raise ValueError("not JSON")
        return self.payload


class KiwoomReadOnlyTests(unittest.TestCase):
    def test_oauth_uses_exact_official_requests_json(self):
        sent = []

        def send(url, **kwargs):
            sent.append((url, kwargs))
            return FakeResponse({"return_code": 0, "token": "MOCK_TOKEN"})

        with patch.dict(os.environ, {
            "GAEMI_KIWOOM_APP_KEY": "TEST_KEY",
            "GAEMI_KIWOOM_APP_SECRET": "TEST_SECRET",
        }), patch.object(kiwoom.requests, "post", side_effect=send):
            self.assertEqual(kiwoom.issue_access_token(), "MOCK_TOKEN")
        self.assertEqual(len(sent), 1)
        url, data = sent[0]
        self.assertEqual(url, "https://api.kiwoom.com/oauth2/token")
        self.assertEqual(data["json"], {
            "grant_type": "client_credentials",
            "appkey": "TEST_KEY", "secretkey": "TEST_SECRET",
        })
        self.assertEqual(data["headers"], {"Content-Type": "application/json;charset=UTF-8"})
        self.assertEqual(data["timeout"], 8)
        self.assertEqual(data["allow_redirects"], False)

    def test_daily_uses_exact_close_and_api_id(self):
        def send(url, **kwargs):
            self.assertEqual(url, "https://api.kiwoom.com/api/us/mrkcond")
            self.assertEqual(kwargs["headers"]["api-id"], "usa20590")
            self.assertEqual(kwargs["headers"]["authorization"], "Bearer MOCK_TOKEN")
            self.assertEqual(kwargs["json"], {"stex_tp": "ND", "stk_cd": "NVDA", "base_dt": "20261019"})
            return FakeResponse({"return_code": 0, "result_list": [
                {"dt": "20261016", "cur_prc": "100", "flu_rt": "1.10"},
                {"dt": "20261019", "cur_prc": "124.25",
                 "flu_rt": "-2.15", "acc_trde_qty": "5,500"},
            ]})

        with patch.object(kiwoom.requests, "post", side_effect=send):
            answer = kiwoom.fetch_us_close(
                "nvda", "nd", dt.date(2026, 10, 19), token="MOCK_TOKEN")
        self.assertEqual(answer["session_date"], "2026-10-19")
        self.assertEqual(answer["close"], 124.25)
        self.assertEqual(answer["change_pct"], -2.15)
        self.assertEqual(answer["volume"], 5500)

    def test_current_quote_fields(self):
        with patch.object(kiwoom.requests, "post", return_value=FakeResponse({
            "return_code": 0, "cur_prc": "220.02", "flu_rt": "+1.64",
            "base_close_pric": "216.47",
        })):
            quote = kiwoom.fetch_us_quote("NVDA", "ND", token="MOCK_TOKEN")
        self.assertEqual(quote["current"], 220.02)
        self.assertEqual(quote["change_pct"], 1.64)
        self.assertEqual(quote["previous_close"], 216.47)
        self.assertFalse(quote["official_close"])

    def test_no_stale_price(self):
        with patch.object(kiwoom.requests, "post", return_value=FakeResponse({
            "return_code": 0, "result_list": [
                {"dt": "20261016", "cur_prc": "100", "flu_rt": "1"},
            ],
        })):
            self.assertIsNone(kiwoom.fetch_us_close(
                "AAPL", "ND", dt.date(2026, 10, 19), token="MOCK_TOKEN"))

    def test_orders_rejected(self):
        with self.assertRaises(kiwoom.KiwoomReadOnlyError):
            kiwoom._market_request("ust20000", {}, "MOCK_TOKEN")

    def test_invalid_symbol(self):
        with self.assertRaises(ValueError):
            kiwoom.fetch_us_close(
                "../../bad", "ND", dt.date(2026, 10, 19), token="MOCK_TOKEN")

    def test_html_response_keeps_secrets_and_body_out_of_error(self):
        raw = b"<html><body>Sample blocked response with internal details</body></html>"
        fake = FakeResponse(status_code=400, headers={"Content-Type": "text/html; charset=UTF-8"}, content=raw)
        with patch.object(kiwoom.requests, "post", return_value=fake):
            with self.assertRaises(kiwoom.KiwoomReadOnlyError) as caught:
                kiwoom._request("/oauth2/token", {"secretkey": "NEVER_LOG_THIS"})
        self.assertEqual(
            str(caught.exception),
            "kiwoom_http_400_content_type_text_html_body_html_like_bytes_" +
            str(len(raw)) + "_page_unknown_server_none_gateway_no"
        )
        self.assertNotIn("Sample blocked", str(caught.exception))
        self.assertNotIn("NEVER_LOG_THIS", str(caught.exception))

    def test_oauth_http_error_empty(self):
        fake = FakeResponse(status_code=400, headers={"Content-Type": "text/plain"}, content=b"")
        with patch.object(kiwoom.requests, "post", return_value=fake):
            with self.assertRaises(kiwoom.KiwoomReadOnlyError) as caught:
                kiwoom._request("/oauth2/token", {})
        self.assertEqual(
            str(caught.exception),
            "kiwoom_http_400_content_type_text_plain_body_empty_bytes_0_page_unknown_server_none_gateway_no"
        )

    def test_oauth_proxy_fingerprint_is_allowlisted(self):
        raw = b"<html><head><title>400 Bad Request</title></head></html>"
        fake = FakeResponse(status_code=400, headers={
            "Content-Type": "text/html", "Server": "nginx/1.26.0",
            "Via": "private proxy data",
        }, content=raw)
        with patch.object(kiwoom.requests, "post", return_value=fake):
            with self.assertRaises(kiwoom.KiwoomReadOnlyError) as caught:
                kiwoom._request("/oauth2/token", {})
        error = str(caught.exception)
        self.assertTrue(error.endswith("_page_bad_request_400_server_nginx_gateway_yes"))
        self.assertNotIn("1.26", error)
        self.assertNotIn("private proxy data", error)

    def test_transport_errors_do_not_expose_exceptions(self):
        with patch.object(kiwoom.requests, "post", side_effect=requests.Timeout("sensitive request")):
            with self.assertRaises(kiwoom.KiwoomReadOnlyError) as caught:
                kiwoom._request("/oauth2/token", {})
        self.assertEqual(str(caught.exception), "kiwoom_request_failed")

    def test_us_index_exchange_codes_never_reach_stock_api(self):
        for exchange, symbol in (("NW", "DJI"), ("NQ", "IXIC"), ("NS", "INX")):
            with self.subTest(exchange=exchange), patch.object(
                kiwoom.requests, "post", side_effect=AssertionError("network call not permitted")
            ):
                with self.assertRaisesRegex(kiwoom.KiwoomReadOnlyError, "kiwoom_invalid_stock_exchange"):
                    kiwoom._request("/api/us/mrkcond", {
                        "stex_tp": exchange, "stk_cd": symbol, "base_dt": "20261021",
                    }, {"api-id": "usa20590", "authorization": "Bearer MOCK_TOKEN"})

    def test_index_symbols_rejected_even_if_exchange_forged(self):
        with patch.object(kiwoom.requests, "post", side_effect=AssertionError("network call not permitted")):
            with self.assertRaisesRegex(kiwoom.KiwoomReadOnlyError, "kiwoom_index_not_stock"):
                kiwoom._market_request("usa20590", {
                    "stex_tp": "ND", "stk_cd": "IXIC", "base_dt": "20261021",
                }, "MOCK_TOKEN")

    def test_unapproved_endpoint_cannot_bypass_allowlist(self):
        with patch.object(kiwoom.requests, "post", side_effect=AssertionError("network call not permitted")):
            with self.assertRaisesRegex(kiwoom.KiwoomReadOnlyError, "kiwoom_unsupported_api_path"):
                kiwoom._request("/api/us/stkinfo", {"index_qry_tp": "%"}, {
                    "api-id": "usa10102", "authorization": "Bearer MOCK_TOKEN",
                })

    def test_api_numeric_error_code_preserved_without_server_message(self):
        fake = FakeResponse({"return_code": 1501, "return_msg": "PRIVATE_USER_DATA"})
        with patch.object(kiwoom.requests, "post", return_value=fake):
            with self.assertRaises(kiwoom.KiwoomReadOnlyError) as caught:
                kiwoom._request("/api/us/mrkcond", {
                    "stex_tp": "ND", "stk_cd": "NVDA", "base_dt": "20261021",
                }, {"api-id": "usa20590", "authorization": "Bearer MOCK_TOKEN"})
        self.assertEqual(str(caught.exception), "kiwoom_api_rejected_code_1501")
        self.assertNotIn("PRIVATE_USER_DATA", str(caught.exception))

    def test_invalid_api_error_code_is_sanitized(self):
        fake = FakeResponse({"return_code": "secret unexpected", "return_msg": "PRIVATE_USER_DATA"})
        with patch.object(kiwoom.requests, "post", return_value=fake):
            with self.assertRaises(kiwoom.KiwoomReadOnlyError) as caught:
                kiwoom._request("/oauth2/token", {})
        self.assertEqual(str(caught.exception), "kiwoom_api_rejected_code_unknown")

    def test_missing_credentials(self):
        with patch.dict(os.environ, {"GAEMI_KIWOOM_APP_KEY": "",
                                     "GAEMI_KIWOOM_APP_SECRET": ""}):
            with self.assertRaises(kiwoom.KiwoomReadOnlyError):
                kiwoom.issue_access_token()


if __name__ == "__main__":
    unittest.main()
