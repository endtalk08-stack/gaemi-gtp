"""The US-close API must return the verified brief produced by the DO worker."""
import unittest
from unittest.mock import patch

from app import app


class USMarketCloseAPITests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

    def test_returns_verified_close_content_and_index_presentation(self):
        brief = {
            "session_date": "2026-11-27",
            "content": "AI 미국장 마감분석\n\n다우존스 48,000.00 (+0.20%)\n\nS&P 500 6,800.00 (+0.35%)",
            "presentation": {
                "session_date_et": "2026-11-27",
                "market_indices": [
                    {"name": "다우존스", "close": 48000.0, "change_pct": 0.2},
                    {"name": "나스닥 종합", "close": 23000.0, "change_pct": 0.4},
                    {"name": "S&P 500", "close": 6800.0, "change_pct": 0.35},
                ],
                "issues": [{"headline": "AI 미국장 마감분석", "summary": "미국 증시는 상승했어.", "tags": []}],
                "response_format": "free_text_v1",
            },
            "published_at": "2026-11-28T07:00:00+09:00",
        }
        with patch("app.read_us_market_close_brief", return_value=brief):
            response = self.client.get("/api/market/us-close")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["available"])
        self.assertEqual(payload["content"], brief["content"])
        self.assertEqual(payload["presentation"], brief["presentation"])
        self.assertEqual(payload["session_date"], "2026-11-27")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_reports_not_ready_when_no_verified_brief_exists(self):
        with patch("app.read_us_market_close_brief", return_value=None):
            response = self.client.get("/api/market/us-close")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True, "available": False})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_reports_read_failure_without_leaking_database_details(self):
        with patch("app.read_us_market_close_brief", side_effect=RuntimeError("private database detail")):
            response = self.client.get("/api/market/us-close")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {
            "ok": False, "available": False, "error": "us_close_unavailable"
        })
        self.assertEqual(response.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
