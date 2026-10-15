import json
import os
import unittest
from unittest.mock import patch
from backend.services.news_issue_ai import select_ai_issues, _validated


class NewsIssueAITests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "NEWS_ISSUE_AI_ENABLED": "1",
            "GROQ_API_KEY": "mock-key",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def candidates(self, index):
        return [{
            "title": "SK하이닉스 CPI 충격 속 반도체주 하락",
            "body": "미국 CPI 발표 이후 반도체주 하락이 나타났다. "
                    "SK하이닉스 주가도 하락했으나 직접 원인은 확인되지 않았다. "
                    + "추가 정보 " * (index + 3),
            "url": "https://news.example/" + str(index),
            "time": "11:30",
            "reaction_at": "2026-10-15T11:30:00+09:00",
        }]

    def answer(self):
        return json.dumps({"issues": [{
            "source_ids": [1], "headline": "반도체주 CPI 충격 이슈",
            "summary": "미국 CPI 발표 이후 반도체주 하락이 나타났다. "
                       "SK하이닉스 주가도 하락했지만 직접 원인은 확인되지 않았다.",
            "tags": ["CPI충격", "반도체주하락"], "category": "market",
            "direction": "negative", "event_key": "cpi_semi_decline",
        }]}, ensure_ascii=False)

    def test_reservation_backgrounds_provider_call(self):
        fallback = [{"headline": "기존"}]
        with patch("backend.database.news_ai_store.reserve_issue_call",
                   return_value=("reserved", [])) as reserve:
            with patch("backend.services.news_issue_ai.threading.Thread") as worker:
                output = select_ai_issues(
                    "SK하이닉스", "국내", self.candidates(0), fallback)
        self.assertEqual(output, fallback)
        self.assertEqual(reserve.call_count, 1)
        worker.return_value.start.assert_called_once()

    def test_daily_limit_returns_latest_without_provider_call(self):
        cached = [{"headline": "저장된 이슈"}]
        with patch("backend.database.news_ai_store.reserve_issue_call",
                   return_value=("exhausted", cached)):
            with patch("backend.services.news_issue_ai.threading.Thread") as worker:
                self.assertEqual(select_ai_issues(
                    "SK하이닉스", "국내", self.candidates(0), []), cached)
                worker.assert_not_called()

    def test_provider_result_is_persisted(self):
        from backend.services.news_issue_ai import _analyze_and_save
        with patch("backend.services.ai_test._groq_answer",
                   return_value=(self.answer(), None, None)) as api:
            with patch("backend.database.news_ai_store.complete_issue_call",
                       return_value=True) as save:
                _analyze_and_save(
                    "SK하이닉스", "KR", "2026-10-15", "hash", self.candidates(0))
        self.assertEqual(api.call_count, 1)
        self.assertEqual(save.call_count, 1)
        self.assertEqual(save.call_args.args[4][0]["headline"],
                         "반도체주 CPI 충격 이슈")

    def test_different_markets_use_local_clock(self):
        from backend.services.news_issue_ai import _day
        self.assertRegex(_day("US"), r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(_day("국내"), r"^\d{4}-\d{2}-\d{2}$")

    def test_rejects_unverified_source_and_invented_number(self):
        data = json.loads(self.answer())
        data["issues"][0]["source_ids"] = [2]
        self.assertEqual(_validated(json.dumps(data), self.candidates(0), "SK하이닉스"), [])
        data["issues"][0]["source_ids"] = [1]
        data["issues"][0]["headline"] = "CPI 9999% 상승 이슈"
        self.assertEqual(_validated(json.dumps(data), self.candidates(0), "SK하이닉스"), [])

    def test_disabled_never_calls_provider(self):
        os.environ["NEWS_ISSUE_AI_ENABLED"] = "0"
        with patch("backend.services.ai_test._groq_answer") as api:
            self.assertEqual(select_ai_issues(
                "SK하이닉스", "국내", self.candidates(0), [{"headline": "기존"}]),
                [{"headline": "기존"}])
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
