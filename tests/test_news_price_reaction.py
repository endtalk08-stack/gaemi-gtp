import datetime
import unittest
from unittest.mock import patch

from backend.providers.market_price import calculate_news_price_reaction
from backend.services.engine import _attach_news_price_reactions


def _iso(timestamp):
    return datetime.datetime.fromtimestamp(
        timestamp,
        tz=datetime.timezone.utc,
    ).isoformat()


class NewsPriceReactionTests(unittest.TestCase):
    def test_calculates_change_from_nearest_news_candle(self):
        rows = [
            {"timestamp": 1200, "close": 100, "high": 101, "low": 99},
            {"timestamp": 1500, "close": 102, "high": 105, "low": 98},
            {"timestamp": 1800, "close": 104, "high": 106, "low": 101},
        ]

        result = calculate_news_price_reaction(rows, _iso(1300))

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["base_price"], 100)
        self.assertEqual(result["current_price"], 104)
        self.assertEqual(result["change_pct"], 4.0)
        self.assertEqual(result["low_pct"], -2.0)
        self.assertEqual(result["high_pct"], 6.0)
        self.assertEqual(result["close_pct"], 4.0)

    def test_exact_five_minute_boundary_uses_previous_close_and_includes_boundary_bar(self):
        rows = [
            {"timestamp": 1200, "close": 100, "high": 101, "low": 99},
            {"timestamp": 1500, "close": 102, "high": 105, "low": 98},
            {"timestamp": 1800, "close": 104, "high": 106, "low": 101},
        ]

        result = calculate_news_price_reaction(rows, _iso(1500))

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["base_price"], 100)
        self.assertEqual(result["low_pct"], -2.0)
        self.assertEqual(result["high_pct"], 6.0)
        self.assertEqual(result["close_pct"], 4.0)

    def test_after_hours_news_uses_last_close_and_starts_at_zero(self):
        rows = [
            {"timestamp": 1200, "close": 100},
            {"timestamp": 1800, "close": 104},
        ]

        result = calculate_news_price_reaction(rows, _iso(3000))

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["base_price"], 104)
        self.assertEqual(result["current_price"], 104)
        self.assertEqual(result["change_pct"], 0.0)
        self.assertIsNone(result["low_pct"])
        self.assertIsNone(result["high_pct"])
        self.assertIsNone(result["close_pct"])

    def test_next_session_keeps_previous_close_as_news_baseline(self):
        rows = [
            {"timestamp": 82800, "close": 100},
            {"timestamp": 90000, "close": 102, "high": 104, "low": 99},
            {"timestamp": 90300, "close": 103, "high": 105, "low": 101},
        ]

        result = calculate_news_price_reaction(rows, _iso(84600))

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["base_price"], 100)
        self.assertEqual(result["current_price"], 103)
        self.assertEqual(result["change_pct"], 3.0)
        self.assertEqual(result["low_pct"], -1.0)
        self.assertEqual(result["high_pct"], 5.0)
        self.assertEqual(result["close_pct"], 3.0)

    @patch("backend.providers.market_price.time.time", return_value=1900)
    def test_live_session_does_not_label_latest_trade_as_close(self, _time):
        rows = [
            {"timestamp": 1200, "close": 100, "high": 101, "low": 99},
            {"timestamp": 1500, "close": 102, "high": 105, "low": 98},
            {"timestamp": 1800, "close": 104, "high": 106, "low": 101},
        ]

        result = calculate_news_price_reaction(rows, _iso(1300))

        self.assertEqual(result["low_pct"], -2.0)
        self.assertEqual(result["high_pct"], 6.0)
        self.assertIsNone(result["close_pct"])


    @patch("backend.services.engine.fetch_news_price_reaction")
    @patch.dict(
        "backend.services.engine.TICKERS",
        {
            "종목A": "AAA",
            "종목B": "BBB",
            "종목C": "CCC",
            "종목D": "DDD",
            "종목E": "EEE",
        },
        clear=False,
    )
    def test_each_issue_can_attach_up_to_three_distinct_stock_reactions(self, fetch_reaction):
        fetch_reaction.return_value = {
            "status": "ready",
            "change_pct": 1.25,
            "low_pct": -2.5,
            "high_pct": 3.75,
            "close_pct": 1.25,
        }
        news_result = {
            "issue_briefs": [
                {
                    "reaction_at": "2026-10-08T14:00:00+00:00",
                    "stock_names": ["종목A", "종목B", "종목C"],
                },
                {
                    "reaction_at": "2026-10-08T15:00:00+00:00",
                    "stock_names": ["종목D", "종목E"],
                },
            ],
        }

        result = _attach_news_price_reactions(news_result)

        self.assertEqual(
            [item["name"] for item in result["issue_briefs"][0]["stock_reactions"]],
            ["종목A", "종목B", "종목C"],
        )
        self.assertEqual(
            [item["name"] for item in result["issue_briefs"][1]["stock_reactions"]],
            ["종목D", "종목E"],
        )
        self.assertEqual(fetch_reaction.call_count, 5)
        self.assertEqual(
            result["issue_briefs"][0]["stock_reactions"][0],
            {
                "name": "종목A",
                "low_pct": -2.5,
                "high_pct": 3.75,
                "close_pct": 1.25,
                "change_pct": 1.25,
            },
        )


if __name__ == "__main__":
    unittest.main()
