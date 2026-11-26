import unittest
from unittest.mock import patch

from backend import kiwoom_us_top20_api as api
from backend.providers import kiwoom_us_quotes


class OperatingQuoteTests(unittest.TestCase):
    def test_rest_qqq_does_not_publish_unverified_vendor_percent(self):
        api._QQQ_REST_CACHE.update(expires_at=0, data=None)
        with patch.object(kiwoom_us_quotes, "fetch_us_quote", return_value={
                "current": 625.31, "change_pct": -3.06}), \
             patch("backend.us_quote_change.validated_change", return_value=(None, None)):
            quote = api._get_qqq_rest_snapshot()
        self.assertEqual(quote["price"], 625.31)
        self.assertIsNone(quote["change_pct"])

    def test_industry_rest_percent_is_hidden_until_live_verification(self):
        with patch.object(api, "_etf_snapshot", return_value=[]), \
             patch("backend.providers.kiwoom_us_industries.fetch_us_etf_quotes", return_value=[{
                 "symbol": "XLK", "change_pct": -9.18, "received_at_ms": 9999999999999
             }]):
            api._US_INDUSTRY_ETF_CACHE.clear()
            quotes = api._get_us_industry_etf_quotes()
        self.assertIsNone(next(q for q in quotes if q["symbol"] == "XLK")["change_pct"])


if __name__ == "__main__":
    unittest.main()
