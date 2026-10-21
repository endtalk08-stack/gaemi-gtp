"""Offline, one-call issue-title test. No actual model requests or DB access."""
import json
import unittest
from unittest.mock import patch

from flask import Flask

from backend.services.issue_title_test import issue_title_test_bp, _CACHE


class IssueTitleIsolationTests(unittest.TestCase):
    def setUp(self):
        _CACHE.clear()
        app = Flask(__name__)
        app.register_blueprint(issue_title_test_bp)
        app.testing = True
        self.client = app.test_client()
        self.quote = "삼성전자와 SK하이닉스의 HBM 시장점유율 격차가 17%포인트로 좁혀졌다."
        self.body = ("SK하이닉스의 분기 실적 전망과 관련해 업계 의견이 엇갈리고 있다. "
                     + self.quote + " "
                     + "실적 전망치와 경쟁사 점유율은 관측 시점에 따라 달라질 수 있다. " * 16)
        self.data = {
            "stock": "SK하이닉스",
            "article_title": "영업이익 전망에도 좁혀진 점유율 격차, HBM4 시험대",
            "source_url": "https://www.thepublic.kr/news/articleView.html?idxno=323135",
            "article_body": self.body,
        }
        self.credentials = patch.dict("os.environ", {
            "AI_TEST_ENABLED": "1",
            "AI_TEST_TOKEN": "one-time-test-password-very-long",
            "CLOUDFLARE_ACCOUNT_ID": "example-account",
            "CLOUDFLARE_API_TOKEN": "example-key",
        })
        self.credentials.start()
        self.addCleanup(self.credentials.stop)
        self.headers = {"Authorization": "Bearer one-time-test-password-very-long"}

    def _post(self, data=None, headers=None):
        return self.client.post("/api/ai-test/issue-title",
                                json=self.data if data is None else data,
                                headers=self.headers if headers is None else headers)

    def _answer(self, quote=None):
        return json.dumps({
            "issue_title": "SK하이닉스, 삼성과 HBM 점유율 격차 축소",
            "main_event": "HBM 점유율 격차가 축소된 것으로 전해졌다.",
            "evidence_quote": self.quote if quote is None else quote,
        }, ensure_ascii=False)

    def test_unauthenticated_request_never_calls_model(self):
        with patch("backend.services.issue_title_test._cloudflare_answer") as model:
            response = self._post(headers={})
        self.assertEqual(response.status_code, 403)
        model.assert_not_called()

    def test_unconfigured_provider_never_calls_model(self):
        with patch.dict("os.environ", {"CLOUDFLARE_ACCOUNT_ID": ""}):
            with patch("backend.services.issue_title_test._cloudflare_answer") as model:
                response = self._post()
        self.assertEqual(response.status_code, 503)
        model.assert_not_called()

    def test_truncated_article_rejected_without_model(self):
        data = {**self.data, "article_body": "short"}
        with patch("backend.services.issue_title_test._cloudflare_answer") as model:
            response = self._post(data)
        self.assertEqual(response.status_code, 400)
        model.assert_not_called()

    def test_overlong_article_rejected_without_model(self):
        data = {**self.data, "article_body": "뉴스 내용 " * 5000}
        with patch("backend.services.issue_title_test._cloudflare_answer") as model:
            response = self._post(data)
        self.assertIn(response.status_code, (400, 413))
        model.assert_not_called()

    def test_full_untrimmed_article_reaches_model_once(self):
        with patch("backend.services.issue_title_test._cloudflare_answer",
                   return_value=(self._answer(),
                                 {"prompt_tokens": 900, "completion_tokens": 70,
                                  "total_tokens": 970}, None)) as model:
            response = self._post()
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertEqual(result["issue_title"], "SK하이닉스, 삼성과 HBM 점유율 격차 축소")
        self.assertTrue(result["quote_found"])
        self.assertTrue(result["review_required"])
        self.assertFalse(result["cached"])
        self.assertEqual(result["usage"]["total_tokens"], 970)
        args, kwargs = model.call_args
        self.assertEqual(args[1]["verified_article_body"], self.body.strip())
        self.assertEqual(kwargs["max_completion_tokens"], 450)
        self.assertEqual(model.call_count, 1)

    def test_same_article_uses_in_process_cache(self):
        with patch("backend.services.issue_title_test._cloudflare_answer",
                   return_value=(self._answer(), {}, None)) as model:
            first = self._post()
            second = self._post()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.get_json()["cached"])
        model.assert_called_once()

    def test_fabricated_quote_does_not_pass(self):
        with patch("backend.services.issue_title_test._cloudflare_answer",
                   return_value=(self._answer("이 원문에는 존재하지 않는 매출 급증 확정 발표다."), {}, None)):
            response = self._post()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"], "evidence_not_in_original")
        self.assertEqual(_CACHE, {})

    def test_withheld_answer(self):
        with patch("backend.services.issue_title_test._cloudflare_answer",
                   return_value=(json.dumps({"issue_title":"보류", "main_event":"",
                                             "evidence_quote":""}, ensure_ascii=False), None, None)):
            response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "withheld")

    def test_no_network_fetch_or_database_calls(self):
        data = {**self.data, "source_url": "https://example.org/news"}
        with patch("backend.services.issue_title_test._cloudflare_answer",
                   return_value=(self._answer(), None, None)):
            result = self._post(data)
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("article_body", result.get_json())


if __name__ == "__main__":
    unittest.main()
