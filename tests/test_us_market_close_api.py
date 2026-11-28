"""The US-close API displays verified index closes without a DB or AI dependency."""
import unittest
from unittest.mock import patch

from app import app


class USMarketCloseAPITests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

    def test_returns_latest_verified_three_index_close(self):
        indices = [
            {"symbol": ".DJI", "name": "다우존스", "session_date_et": "2026-11-27",
             "close": 48000.0, "change": 96.0, "change_pct": 0.20},
            {"symbol": ".IXIC", "name": "나스닥 종합", "session_date_et": "2026-11-27",
             "close": 23000.0, "change": 92.0, "change_pct": 0.40},
            {"symbol": ".INX", "name": "S&P 500", "session_date_et": "2026-11-27",
             "close": 6800.0, "change": 23.8, "change_pct": 0.35},
        ]
        with patch("app.read_verified_us_indices", return_value=indices) as reader:
            response = self.client.get("/api/market/us-close")

        reader.assert_called_once_with()
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["available"])
        self.assertEqual(payload["session_date"], "2026-11-27")
        self.assertEqual(payload["presentation"]["market_indices"], indices)
        self.assertEqual(payload["presentation"]["issues"], [])
        self.assertIn("다우존스 48,000.00 (+0.20%)", payload["content"])
        self.assertIn("S&P 500 6,800.00 (+0.35%)", payload["content"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_returns_unavailable_when_provider_has_no_verified_close(self):
        with patch("app.read_verified_us_indices", side_effect=ValueError("no completed session")):
            response = self.client.get("/api/market/us-close")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {
            "ok": False, "available": False, "error": "us_close_unavailable"
        })
        self.assertEqual(response.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
