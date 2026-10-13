"""Regression tests for Naver stock-code industry mapping, shared across tabs."""
import json
import threading
import time
import unittest
from unittest.mock import patch

from backend.providers import market_industry
from backend.services import market_rankings


class IndustrySourceTests(unittest.TestCase):
    def setUp(self):
        market_industry.INDUSTRY_CACHE.clear()

    def _response(self, data):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return json.dumps(data).encode("utf-8")
        return Response()

    def test_domestic_profile_is_fetched_once_for_both_ranking_menus(self):
        response = self._response({
            "itemCode": "005930", "industryCode": "278",
            "industryName": "반도체와반도체장비",
        })
        with patch.object(market_industry.urllib.request, "urlopen", return_value=response) as req:
            popular = market_industry.get_stock_industries("kr", ["005930"])
            turnover = market_industry.get_stock_industries("kr", ["005930"])
        self.assertEqual(popular, {"005930": "반도체와반도체장비"})
        self.assertEqual(turnover, popular)
        self.assertEqual(req.call_count, 1)
        self.assertIn(
            "/api/stockSecurity/items/v2/domestic/005930/profile",
            req.call_args.args[0].full_url,
        )

    def test_us_prices_uses_one_batch_and_reuses_labels(self):
        response = self._response({
            "NVDA.O": {"itemCode": "NVDA.O", "sectorName": "반도체"},
            "AAPL.O": {"itemCode": "AAPL.O", "sectorName": "기술"},
        })
        with patch.object(market_industry.urllib.request, "urlopen", return_value=response) as req:
            first = market_industry.get_stock_industries("us", ["NVDA.O", "AAPL.O"])
            second = market_industry.get_stock_industries("us", ["AAPL.O", "NVDA.O"])
        self.assertEqual(first, {"NVDA.O": "반도체", "AAPL.O": "기술"})
        self.assertEqual(first, second)
        self.assertEqual(req.call_count, 1)
        from urllib.parse import parse_qs, urlparse
        url = urlparse(req.call_args.args[0].full_url)
        self.assertEqual(url.path, "/api/stockSecurity/items/v1/foreign/prices")
        self.assertEqual(parse_qs(url.query)["itemCodes"], ["NVDA.O", "AAPL.O"])

    def test_upstream_ranking_industry_seeds_shared_cache(self):
        with patch.object(market_industry.urllib.request, "urlopen") as req:
            labels = market_industry.get_stock_industries("us", ["NVDA.O"], known={"NVDA.O": "반도체"})
            labels2 = market_industry.get_stock_industries("us", ["NVDA.O"])
        self.assertEqual(labels, {"NVDA.O": "반도체"})
        self.assertEqual(labels2, labels)
        req.assert_not_called()

    def test_kr_missing_label_is_blank_and_negative_cached(self):
        with patch.object(
            market_industry.urllib.request, "urlopen",
            return_value=self._response({"itemCode": "005930"}),
        ) as req:
            self.assertEqual(market_industry.get_stock_industries("kr", ["005930"]), {})
            self.assertEqual(market_industry.get_stock_industries("kr", ["005930"]), {})
        self.assertEqual(req.call_count, 1)

    def test_failures_can_retry_after_cooldown(self):
        with patch.object(market_industry.urllib.request, "urlopen", side_effect=OSError("offline")) as req:
            with patch.object(market_industry.time, "monotonic", return_value=1000):
                self.assertEqual(market_industry.get_stock_industries("kr", ["005930"]), {})
            with patch.object(market_industry.time, "monotonic", return_value=1005):
                self.assertEqual(market_industry.get_stock_industries("kr", ["005930"]), {})
            with patch.object(market_industry.time, "monotonic", return_value=1035):
                self.assertEqual(market_industry.get_stock_industries("kr", ["005930"]), {})
        self.assertEqual(req.call_count, 2)

    def test_invalid_codes_are_never_sent_to_naver(self):
        with patch.object(market_industry.urllib.request, "urlopen") as req:
            self.assertEqual(market_industry.get_stock_industries("kr", ["", "../oops", "INVALID!!!"]), {})
            self.assertEqual(market_industry.get_stock_industries("us", ["", "AAA?itemCodes=XXX"]), {})
        req.assert_not_called()

    def test_simultaneous_requests_do_not_collect_same_code_twice(self):
        def slow(_req, timeout):
            time.sleep(0.03)
            return self._response({"itemCode": "005930", "industryName": "반도체"})
        results = []
        with patch.object(market_industry.urllib.request, "urlopen", side_effect=slow) as req:
            t1 = threading.Thread(target=lambda: results.append(market_industry.get_stock_industries("kr", ["005930"])))
            t2 = threading.Thread(target=lambda: results.append(market_industry.get_stock_industries("kr", ["005930"])))
            t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(req.call_count, 1)
        self.assertEqual(results, [{"005930": "반도체"}, {"005930": "반도체"}])

    def test_all_four_rankings_share_industry_result_by_code(self):
        kr_raw = {"items": [{"itemCode": "005930", "price": {
            "itemName": "삼성전자", "krx": {"currentPrice": "234000", "tradingValue": "5916362000000"},
        }}]}
        us_raw = {"items": [{"itemCode": "NVDA.O", "price": {
            "itemName": "엔비디아", "currentPrice": "225.7850",
        }}]}
        def fake_naver(request, timeout):
            url = request.full_url
            if "/domestic/005930/profile" in url:
                return self._response({"itemCode": "005930", "industryName": "반도체와반도체장비"})
            if "/foreign/prices" in url:
                return self._response({"NVDA.O": {"sectorName": "반도체"}})
            raise AssertionError(f"Unexpected Naver request: {url}")
        with patch.object(market_industry.urllib.request, "urlopen", side_effect=fake_naver) as req:
            with patch.object(market_rankings, "fetch_kr_popular_ranking_raw", return_value=kr_raw):
                kr_pop = market_rankings.build_kr_popular_result()
            with patch.object(market_rankings, "fetch_kr_trading_value_ranking_raw", return_value=kr_raw):
                kr_value = market_rankings.build_kr_trading_value_result()
            with patch.object(market_rankings, "fetch_us_popular_ranking_raw", return_value=us_raw):
                us_pop = market_rankings.build_us_popular_result()
            with patch.object(market_rankings, "fetch_us_trading_value_ranking_raw", return_value=us_raw):
                us_value = market_rankings.build_us_trading_value_result()
        self.assertEqual([kr_pop[0]["industry"], kr_value[0]["industry"]],
                         ["반도체와반도체장비"] * 2)
        self.assertEqual([us_pop[0]["industry"], us_value[0]["industry"]], ["반도체"] * 2)
        self.assertEqual(kr_pop[0]["price"], 234000.0)
        self.assertEqual(us_pop[0]["price"], 225.785)
        self.assertEqual(req.call_count, 2, "One KR code + one US batch, not four per-menu requests")


if __name__ == "__main__":
    unittest.main()
