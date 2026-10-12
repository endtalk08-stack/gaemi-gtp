"""Market-wide questions must not be mistaken for a missing stock name."""
import unittest
from unittest.mock import patch

from flask import Flask

from backend.services.ai_test import ai_test_bp, _is_market_gainers_question


class MarketGainersQuestionTests(unittest.TestCase):
    def test_market_wide_phrases(self):
        questions = [
            "오늘 상승 종목 알려줘",
            "오늘 상승한 종목 보여줘",
            "오늘 급등주 알려줘",
            "오늘 상승률 TOP 20",
            "오늘 많이 오른 종목은?",
        ]
        with patch("backend.services.ai_test._question_stock", return_value=""):
            for question in questions:
                with self.subTest(question=question):
                    self.assertTrue(_is_market_gainers_question(question))

    def test_individual_stock_questions_stay_individual(self):
        with patch("backend.services.ai_test._question_stock", return_value=""):
            self.assertFalse(_is_market_gainers_question("삼성전자 이슈뭐야~"))
            self.assertFalse(_is_market_gainers_question("삼성전자 상승률 알려줘"))
        with patch("backend.services.ai_test._question_stock", return_value="SK하이닉스"):
            self.assertFalse(_is_market_gainers_question("SK하이닉스 상승 종목이야?"))

    def test_market_question_ignores_old_selected_stock_and_skips_ai(self):
        app = Flask(__name__)
        app.register_blueprint(ai_test_bp)
        with (
            patch("backend.services.ai_test._authorized", return_value=False),
            patch("backend.services.private_access.private_enabled", return_value=True),
            patch("backend.services.private_access._authorized", return_value=True),
            patch("backend.services.ai_test._question_stock", return_value=""),
            patch("backend.services.ai_test._remaining", return_value={}),
            patch("backend.services.ai_test._groq_answer", side_effect=AssertionError("AI should not run")),
        ):
            response = app.test_client().post(
                "/api/ai-test/chat",
                json={
                    "role": "news",
                    "stock": "삼성전자",
                    "question": "오늘 상승 종목 알려줘",
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["stock"], "")
        self.assertEqual(payload["model"], "market-ranking-unavailable")
        self.assertIn("순위 데이터", payload["answer"])


if __name__ == "__main__":
    unittest.main()
