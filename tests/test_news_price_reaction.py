import datetime
import unittest

from backend.providers.market_price import calculate_news_price_reaction


def _iso(timestamp):
    return datetime.datetime.fromtimestamp(
        timestamp,
        tz=datetime.timezone.utc,
    ).isoformat()


class NewsPriceReactionTests(unittest.TestCase):
    def test_calculates_change_from_nearest_news_candle(self):
        rows = [
            {"timestamp": 1200, "close": 100},
            {"timestamp": 1500, "close": 102},
            {"timestamp": 1800, "close": 104},
        ]

        result = calculate_news_price_reaction(rows, _iso(1300))

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["base_price"], 100)
        self.assertEqual(result["current_price"], 104)
        self.assertEqual(result["change_pct"], 4.0)

    def test_waits_when_news_is_newer_than_latest_trade(self):
        rows = [
            {"timestamp": 1200, "close": 100},
            {"timestamp": 1800, "close": 104},
        ]

        result = calculate_news_price_reaction(rows, _iso(3000))

        self.assertEqual(result["status"], "waiting")
        self.assertIsNone(result["change_pct"])

    def test_uses_first_trade_after_pre_market_news(self):
        rows = [
            {"timestamp": 3600, "close": 100},
            {"timestamp": 3900, "close": 101},
            {"timestamp": 4200, "close": 103},
        ]

        result = calculate_news_price_reaction(rows, _iso(3000))

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["base_price"], 100)
        self.assertEqual(result["change_pct"], 3.0)


if __name__ == "__main__":
    unittest.main()
