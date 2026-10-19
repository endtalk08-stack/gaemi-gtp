"""Korean Naver quote regression: optional '-' must not hide a real price."""
import io
import json
import unittest
from unittest.mock import patch

from backend.providers import market_price
from backend.analysis.price.quote import build_price_result


class KoreanQuoteParsingTests(unittest.TestCase):
    def setUp(self):
        market_price.KR_QUOTE_CACHE.clear()

    def tearDown(self):
        market_price.KR_QUOTE_CACHE.clear()

    def _fetch(self, row):
        data = json.dumps({"datas": [row]}).encode("utf-8")
        with patch.object(
            market_price.urllib.request, "urlopen", return_value=io.BytesIO(data)
        ) as request:
            result = market_price.fetch_kr_stock_quote("005930")
        request.assert_called_once()
        return result

    def test_optional_missing_fields_preserve_current(self):
        current, diff, change, high, low = self._fetch({
            "closePrice": "101,200",
            "compareToPreviousClosePrice": "-",
            "fluctuationsRatio": "-",
            "highPrice": "102,000",
            "lowPrice": "-",
        })
        self.assertEqual(current, 101200.0)
        self.assertIsNone(diff)
        self.assertIsNone(change)
        self.assertEqual(high, 102000.0)
        self.assertIsNone(low)
        self.assertEqual(build_price_result(
            is_krw=True, current=current, change_pct=change, high=high, low=low
        )["price_text"], "101,200원")

    def test_normal_full_response_is_unchanged(self):
        self.assertEqual(
            self._fetch({
                "closePrice": "101,200",
                "compareToPreviousClosePrice": "1,200",
                "fluctuationsRatio": "1.20",
                "highPrice": "102,000",
                "lowPrice": "100,500",
            }),
            (101200.0, 1200.0, 1.2, 102000.0, 100500.0),
        )

    def test_missing_real_price_does_not_invent_one(self):
        for bad in ("-", "", None, "nan", "0"):
            with self.subTest(bad=bad):
                market_price.KR_QUOTE_CACHE.clear()
                self.assertEqual(
                    self._fetch({
                        "closePrice": bad,
                        "compareToPreviousClosePrice": "1000",
                        "fluctuationsRatio": "1",
                        "highPrice": "102000",
                        "lowPrice": "100000",
                    }),
                    (None, None, None, None, None),
                )

    def test_invalid_optional_nonfinite_values_are_ignored(self):
        self.assertEqual(
            self._fetch({
                "closePrice": "105,000",
                "compareToPreviousClosePrice": "nan",
                "fluctuationsRatio": "inf",
                "highPrice": "-",
                "lowPrice": "0",
            }),
            (105000.0, None, None, None, None),
        )


if __name__ == "__main__":
    unittest.main()
