import datetime
import unittest
from unittest.mock import patch

from backend.providers.market_price import calculate_news_price_reaction
from backend.services.engine import _attach_news_price_reactions
from backend.services.ai_test import _context


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



    def test_ai_chat_context_receives_the_same_reaction_range_as_central(self):
        issues = [
            {
                "headline": "목표주가 상향 이슈",
                "summary": "삼성SDI 목표주가를 상향했다.",
                "reaction_at": "2026-10-14T00:24:00+00:00",
                "stock_reactions": [
                    {
                        "name": "삼성SDI", "low_pct": -0.52, "high_pct": 3.27,
                        "close_pct": 1.5, "change_pct": 2.0,
                    },
                ],
            },
            {
                "headline": "생산 확대 이슈",
                "summary": "생산 계획을 발표했다.",
                "reaction_at": "2026-10-14T23:40:00+00:00",
                "stock_reactions": [
                    {"name": "삼성SDI", "low_pct": 0.0, "high_pct": 7.33},
                ],
            },
        ]
        context = _context("삼성SDI", {"issue_briefs": issues})
        self.assertEqual(context["issue_briefs"][0]["stock_reactions"], [
            {"name": "삼성SDI", "low_pct": -0.52, "high_pct": 3.27},
        ])
        self.assertEqual(context["issue_briefs"][1]["stock_reactions"], [
            {"name": "삼성SDI", "low_pct": 0.0, "high_pct": 7.33},
        ])
        self.assertEqual(context["issue_briefs"][0]["reaction_at"], issues[0]["reaction_at"])
        self.assertIn("첫 거래 세션", context["note"])
        self.assertNotIn("change_pct", context["issue_briefs"][0]["stock_reactions"][0])
        self.assertNotIn("close_pct", context["issue_briefs"][0]["stock_reactions"][0])

    def test_ai_chat_context_drops_missing_or_nonfinite_reactions(self):
        context = _context("삼성SDI", {"issue_briefs": [
            {
                "headline": "이슈",
                "summary": "내용",
                "stock_reactions": [
                    {"name": "삼성SDI", "low_pct": None, "high_pct": 2.0},
                    {"name": "삼성SDI", "low_pct": -1.0, "high_pct": float("nan")},
                    {"name": "삼성SDI", "low_pct": -1.0, "high_pct": 3.0},
                ],
            },
            {
                "headline": "두 번째 이슈", "summary": "내용",
            },
        ]})
        self.assertEqual(context["issue_briefs"][0]["stock_reactions"], [
            {"name": "삼성SDI", "low_pct": -1.0, "high_pct": 3.0},
        ])
        self.assertEqual(context["issue_briefs"][1]["stock_reactions"], [])

if __name__ == "__main__":
    unittest.main()
