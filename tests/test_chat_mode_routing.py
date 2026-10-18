"""Offline regression tests for the existing central chat mode switch."""
import unittest
from unittest.mock import patch

from flask import Flask

from backend.services import ai_test as chat


class ChatModeRoutingTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(chat.ai_test_bp)
        self.client = app.test_client()

    def site(self):
        """Fake only the existing private preview session; no live providers."""
        import contextlib
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(chat, "_authorized", return_value=False))
        stack.enter_context(patch("backend.services.private_access.private_enabled", return_value=True))
        stack.enter_context(patch("backend.services.private_access._authorized", return_value=True))
        stack.enter_context(patch.object(chat, "_question_stock", return_value=""))
        return stack

    def test_gaemi_cannot_call_ai_even_with_forged_role(self):
        with self.site(), patch.object(chat, "_groq_answer") as provider, \
             patch.object(chat, "_cloudflare_answer") as cf_provider:
            for body in (
                {"question": "내일 날씨 알려줘", "role": "deep"},
                {"question": "내일 날씨 알려줘", "app_mode": "gaemi", "role": "news"},
                {"question": "내일 날씨 알려줘", "app_mode": "gaemi", "role": "cloudflare"},
            ):
                response = self.client.post("/api/ai-test/chat", json=body)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json["error"], "ai_mode_disabled")
            provider.assert_not_called()
            cf_provider.assert_not_called()

    def test_info_and_pro_use_spare_models_without_local_caps(self):
        for mode, role, expected in (
            ("info", "cloudflare", "@cf/openai/gpt-oss-20b"),
            ("pro", "compare", "qwen/qwen3.8-27b"),
        ):
            with self.subTest(mode=mode):
                with self.site(), \
                     patch.object(chat, "_private_provider_ready", return_value=True), \
                     patch.object(chat, "_take_slot") as artificial_cap, \
                     patch.object(chat, "_groq_answer", return_value=("Groq 성공", {}, {})) as groq, \
                     patch.object(chat, "_cloudflare_answer", return_value=("Cloudflare 성공", {}, {})) as cf:
                    response = self.client.post("/api/ai-test/chat", json={
                        "question": "대답해 줘", "app_mode": mode, "role": "deep",
                    })
                    self.assertEqual(response.status_code, 200, response.json)
                    self.assertEqual(response.json["model"], expected)
                    artificial_cap.assert_not_called()
                    if role == "cloudflare":
                        cf.assert_called_once()
                        groq.assert_not_called()
                    else:
                        groq.assert_called_once()
                        self.assertEqual(groq.call_args.args[0], expected)
                        cf.assert_not_called()

    def test_info_prompt_is_opt_in_and_pro_remains_unchanged(self):
        with self.site(), patch.object(chat, "_private_provider_ready", return_value=True), \
             patch.object(chat, "_cloudflare_answer", return_value=("성공", {}, {})) as cf, \
             patch.object(chat, "_groq_answer", return_value=("성공", {}, {})) as groq:
            info = self.client.post("/api/ai-test/chat", json={
                "question": "설명해 줘", "app_mode": "info",
            })
            self.assertEqual(info.status_code, 200)
            self.assertEqual(
                cf.call_args.kwargs["style_prompt"], chat.INFO_STYLE_PROMPT
            )
            self.assertEqual(
                chat.INFO_STYLE_PROMPT,
                "답변은 간결하게 작성하고, 불필요한 표와 코드블록은 사용하지 마."
            )
            pro = self.client.post("/api/ai-test/chat", json={
                "question": "설명해 줘", "app_mode": "pro",
            })
            self.assertEqual(pro.status_code, 200)
            self.assertIsNone(groq.call_args.kwargs["style_prompt"])

    def test_cloudflare_prompt_appends_only_when_requested(self):
        import json
        import os
        from unittest.mock import MagicMock

        requests = []

        def stub_urlopen(request, timeout):
            requests.append(json.loads(request.data.decode("utf-8")))
            response = MagicMock()
            response.read.return_value = json.dumps({
                "choices": [{"message": {"content": "정상 답변"}}]
            }).encode("utf-8")
            response.headers = {}
            response.__enter__.return_value = response
            return response

        with patch.dict(os.environ, {
            "CLOUDFLARE_ACCOUNT_ID": "test-account",
            "CLOUDFLARE_API_TOKEN": "test-token",
        }), patch.object(chat.urllib.request, "urlopen", side_effect=stub_urlopen):
            chat._cloudflare_answer("질문", {"stock": ""}, style_prompt=chat.INFO_STYLE_PROMPT)
            chat._cloudflare_answer("질문", {"stock": ""}, style_prompt=None)
        self.assertEqual(
            requests[0]["messages"][0]["content"],
            chat.SYSTEM_PROMPT + "\n" + chat.INFO_STYLE_PROMPT,
        )
        self.assertEqual(requests[1]["messages"][0]["content"], chat.SYSTEM_PROMPT)
        self.assertEqual(requests[0]["model"], requests[1]["model"])

    def test_no_stock_info_question_does_not_collect_stock_news(self):
        with self.site(), patch.object(chat, "_private_provider_ready", return_value=True), \
             patch.object(chat, "_take_slot") as artificial_cap, \
             patch.object(chat, "_cloudflare_answer", return_value=("일반 질문 답변", {}, {})) as provider:
            r = self.client.post("/api/ai-test/chat", json={
                "question": "AI가 뭔지 설명해줘", "app_mode": "info"})
            self.assertEqual(r.status_code, 200, r.json)
            self.assertEqual(provider.call_args.args[1]["stock"], "")
            artificial_cap.assert_not_called()

    def test_missing_cloudflare_credential_fails_before_provider(self):
        with self.site(), patch.object(chat, "_private_provider_ready", return_value=False), \
             patch.object(chat, "_cloudflare_answer") as provider:
            r = self.client.post("/api/ai-test/chat", json={
                "question": "질문", "app_mode": "info"})
            self.assertEqual(r.status_code, 503, r.json)
            provider.assert_not_called()

    def test_provider_native_rate_limits_are_reported(self):
        import io
        import urllib.error
        err = urllib.error.HTTPError(
            "https://api.cloudflare.com/", 429, "rate limited", {},
            io.BytesIO(b'{"error":"limit reached"}'),
        )
        with self.site(), patch.object(chat, "_private_provider_ready", return_value=True), \
             patch.object(chat, "_cloudflare_answer", side_effect=err), \
             patch.object(chat, "_take_slot") as artificial_cap:
            r = self.client.post("/api/ai-test/chat", json={
                "question": "질문", "app_mode": "info"})
            self.assertEqual(r.status_code, 429)
            self.assertEqual(r.json["error"], "cloudflare_rate_limit")
            artificial_cap.assert_not_called()

    def test_unknown_mode_rejected_without_provider(self):
        with self.site(), patch.object(chat, "_groq_answer") as provider:
            r = self.client.post("/api/ai-test/chat", json={
                "question": "질문", "app_mode": "superpro"})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.json["error"], "unsupported_mode")
            provider.assert_not_called()

    def test_unauthenticated_cannot_call_provider(self):
        with patch.object(chat, "_authorized", return_value=False), \
             patch("backend.services.private_access.private_enabled", return_value=False), \
             patch.object(chat, "_groq_answer") as provider:
            r = self.client.post("/api/ai-test/chat", json={
                "question": "질문", "app_mode": "pro"})
            self.assertEqual(r.status_code, 403)
            provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
