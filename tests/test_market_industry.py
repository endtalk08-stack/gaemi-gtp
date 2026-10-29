"""Only the retained US trading-value industry lookup may reach Naver."""
import json
import unittest
from unittest.mock import patch

from backend.providers import market_industry


class IndustrySourceTests(unittest.TestCase):
    def setUp(self):
        market_industry.INDUSTRY_CACHE.clear()

    def test_us_batch_industry_is_shared_and_cached(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self):
                return json.dumps({
                    "NVDA.O": {"sectorName": "반도체"},
                    "AAPL.O": {"sectorName": "기술"},
                }).encode("utf-8")

        with patch.object(market_industry.urllib.request, "urlopen",
                          return_value=Response()) as urlopen:
            first = market_industry.get_stock_industries("us", ["NVDA.O", "AAPL.O"])
            second = market_industry.get_stock_industries("us", ["AAPL.O", "NVDA.O"])
        self.assertEqual(first, {"NVDA.O": "반도체", "AAPL.O": "기술"})
        self.assertEqual(first, second)
        urlopen.assert_called_once()

    def test_domestic_industry_no_longer_calls_provider(self):
        with patch.object(market_industry.urllib.request, "urlopen") as request:
            self.assertEqual(
                market_industry.get_stock_industries("kr", ["005930"]), {})
        request.assert_not_called()

    def test_known_us_sector_does_not_refetch(self):
        with patch.object(market_industry.urllib.request, "urlopen") as request:
            self.assertEqual(
                market_industry.get_stock_industries(
                    "us", ["NVDA.O"], known={"NVDA.O": "반도체"}),
                {"NVDA.O": "반도체"},
            )
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
