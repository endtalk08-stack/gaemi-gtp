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
        with self.site(), patch.object(chat, "_groq_answer") as provider:
            for body in (
                {"question": "내일 날씨 알려줘", "role": "deep"},
                {"question": "내일 날씨 알려줘", "app_mode": "gaemi", "role": "news"},
                {"question": "내일 날씨 알려줘", "app_mode": "gaemi", "role": "cloudflare"},
            ):
                response = self.client.post("/api/ai-test/chat", json=body)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json["error"], "ai_mode_disabled")
            provider.assert_not_called()

    def test_info_and_pro_are_server_selected_not_client_model(self):
        for mode, expected in (("info", "openai/gpt-oss-20b"),
                               ("pro", "openai/gpt-oss-120b")):
            with self.subTest(mode=mode):
                with self.site(), patch.object(chat, "_settings_ready", return_value=True), \
                     patch.object(chat, "_take_slot", return_value=None) as quota, \
                     patch.object(chat, "_groq_answer", return_value=("답변 성공", {}, {})) as provider:
                    response = self.client.post("/api/ai-test/chat", json={
                        "question": "대답해 줘", "app_mode": mode, "role": "compare",
                    })
                    self.assertEqual(response.status_code, 200, response.json)
                    self.assertEqual(response.json["model"], expected)
                    self.assertEqual(provider.call_args.args[0], expected)
                    quota.assert_called_once_with("news" if mode == "info" else "deep")

    def test_no_stock_info_question_does_not_collect_stock_news(self):
        with self.site(), patch.object(chat, "_settings_ready", return_value=True), \
             patch.object(chat, "_take_slot", return_value=None), \
             patch.object(chat, "_groq_answer", return_value=("일반 질문 답변", {}, {})) as provider:
            r = self.client.post("/api/ai-test/chat", json={
                "question": "AI가 뭔지 설명해줘", "app_mode": "info"})
            self.assertEqual(r.status_code, 200, r.json)
            self.assertEqual(provider.call_args.args[2]["stock"], "")

    def test_private_quota_prevents_provider_calls(self):
        with self.site(), patch.object(chat, "_settings_ready", return_value=True), \
             patch.object(chat, "_take_slot", return_value="minute_limit"), \
             patch.object(chat, "_groq_answer") as provider:
            r = self.client.post("/api/ai-test/chat", json={
                "question": "질문", "app_mode": "pro"})
            self.assertEqual(r.status_code, 429)
            self.assertEqual(r.json["error"], "minute_limit")
            provider.assert_not_called()

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
