"""Regression test for preserving official US industry percentage changes."""
import unittest
from unittest.mock import patch

from backend import kiwoom_us_top20_api as api


class USIndustryChangePreservationTests(unittest.TestCase):
    def test_industry_change_pct_survives_stock_quote_fallback(self):
        source = {
            "items": [{
                "key": "semiconductors",
                "name": "반도체",
                "change_pct": 1.25,
                "stocks": [{
                    "symbol": "NVDA",
                    "price": None,
                    "exchange": None,
                    "change_pct": 2.0,
                }],
            }]
        }

        with patch.object(api, "_get_us_industry_map", return_value=source), \
             patch.object(api, "_us_close_get", return_value=None):
            result = api._get_us_industry_map_with_stocks("legacy")

        self.assertEqual(result["items"][0]["change_pct"], 1.25)
        self.assertIsNone(result["items"][0]["stocks"][0]["change_pct"])


if __name__ == "__main__":
    unittest.main()
