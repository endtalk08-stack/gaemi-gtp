"""Offline regression tests: DO AI must not use a stale or mismatched price."""
import importlib.util
import io
import json
import pathlib
import unittest
from unittest.mock import patch

PATH = pathlib.Path(__file__).resolve().parents[1] / "ops" / "staged_us_quote_context.py"
spec = importlib.util.spec_from_file_location("staged_us_quote_context", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class VerifiedAIPriceTests(unittest.TestCase):
    NOW = 1792800000000

    def payload(self, symbol="NVDA", **overrides):
        row = {
            "symbol": symbol,
            "price": 210.75,
            "change_pct": -1.24,
            "received_at_ms": self.NOW - 4000,
            "stale": False,
        }
        row.update(overrides)
        return {"ok": True, "market": "us", "source": "kiwoom-direct", "items": [row]}

    def test_verified_fresh_price_only(self):
        result = module.verified_price_context("엔비디아", self.payload(), now_ms=self.NOW)
        self.assertEqual(result["symbol"], "NVDA")
        self.assertEqual(result["current_price"], 210.75)
        self.assertEqual(result["change_pct"], -1.24)
        self.assertEqual(result["quote_source"], "kiwoom-direct")
        self.assertEqual(result["status"], "fresh")

    def test_stock_identity_mismatch_is_not_accepted(self):
        self.assertIsNone(module.verified_price_context(
            "테슬라", self.payload("NVDA"), now_ms=self.NOW))
        self.assertIsNone(module.verified_price_context(
            "알파벳 Class A", self.payload("GOOG"), now_ms=self.NOW))
        self.assertIsNone(module.verified_price_context(
            "미확인종목", self.payload(), now_ms=self.NOW))

    def test_stale_old_future_and_missing_freshness(self):
        for overrides in (
            {"stale": True},
            {"stale": None},
            {"received_at_ms": self.NOW - 26000},
            {"received_at_ms": self.NOW + 4000},
            {"received_at_ms": "wrong"},
        ):
            with self.subTest(overrides=overrides):
                self.assertIsNone(module.verified_price_context(
                    "엔비디아", self.payload(**overrides), now_ms=self.NOW))

    def test_malformed_market_provider_price_and_change(self):
        sample = self.payload()
        for key, value in (("ok", False), ("market", "kr"), ("source", "yahoo-daily"),
                           ("items", []), ("items", "invalid")):
            row = dict(sample)
            row[key] = value
            with self.subTest(key=key):
                self.assertIsNone(module.verified_price_context(
                    "엔비디아", row, now_ms=self.NOW))
        for changes in ({"price": 0}, {"price": float("nan")}, {"price": "210"},
                        {"change_pct": float("inf")}, {"change_pct": "1.0"}):
            with self.subTest(changes=changes):
                self.assertIsNone(module.verified_price_context(
                    "엔비디아", self.payload(**changes), now_ms=self.NOW))

    def test_empty_change_is_not_fabricated(self):
        result = module.verified_price_context(
            "엔비디아", self.payload(change_pct=None), now_ms=self.NOW)
        self.assertIsNone(result["change_pct"])

    def test_reader_reuses_single_existing_render_feed(self):
        calls = []
        def opener(request, timeout):
            calls.append((request.full_url, timeout))
            return io.BytesIO(json.dumps(self.payload()).encode("utf-8"))
        with patch.dict("os.environ", {"GAEMI_US_QUOTE_FEED_URL": module.DEFAULT_FEED_URL}):
            found = module.fetch_verified_us_price_context(
                "엔비디아", opener=opener, now_ms=self.NOW)
        self.assertEqual(found["current_price"], 210.75)
        self.assertEqual(calls, [(module.DEFAULT_FEED_URL, 3)])

    def test_unknown_stock_or_wrong_endpoint_does_not_call_api(self):
        calls = []
        def opener(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("network must not be called")
        self.assertIsNone(module.fetch_verified_us_price_context(
            "unknown", opener=opener, now_ms=self.NOW))
        with patch.dict("os.environ", {
            "GAEMI_US_QUOTE_FEED_URL": "https://evil.test/market/us-live-quotes"
        }):
            self.assertIsNone(module.fetch_verified_us_price_context(
                "엔비디아", opener=opener, now_ms=self.NOW))
        self.assertEqual(calls, [])

    def test_network_or_bad_json_fails_closed(self):
        def bad_network(request, timeout):
            raise OSError("no network")
        def bad_json(request, timeout):
            return io.BytesIO(b'not JSON')
        self.assertIsNone(module.fetch_verified_us_price_context(
            "엔비디아", opener=bad_network, now_ms=self.NOW))
        self.assertIsNone(module.fetch_verified_us_price_context(
            "엔비디아", opener=bad_json, now_ms=self.NOW))


if __name__ == "__main__":
    unittest.main()
