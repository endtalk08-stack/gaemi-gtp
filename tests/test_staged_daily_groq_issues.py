"""Offline validation checks for staged Groq issue selection."""
import importlib.util
import json
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "ops" / "staged_daily_groq_issues.py"
spec = importlib.util.spec_from_file_location("staged_daily_groq_issues", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GroqIssueTests(unittest.TestCase):
    def test_empty_issues(self):
        self.assertEqual(module.parse_issues('{"issues":[]}'), [])

    def test_three_issues(self):
        item = {"headline": "기사 제목", "summary": "쉬운 내용", "tags": ["#주식"]}
        self.assertEqual(len(module.parse_issues(json.dumps({"issues": [item] * 3}))), 3)

    def test_reject_four(self):
        item = {"headline": "제목", "summary": "내용", "tags": []}
        with self.assertRaises(ValueError):
            module.parse_issues(json.dumps({"issues": [item] * 4}))

    def test_reject_wrong_fields(self):
        with self.assertRaises(ValueError):
            module.parse_issues('{"issues":[{"title":"x","summary":"y","tags":[]}]}')

    def test_reject_bad_tags(self):
        with self.assertRaises(ValueError):
            module.parse_issues('{"issues":[{"headline":"x","summary":"y","tags":["x"]}]}')

    def test_no_news_does_not_call_api(self):
        self.assertEqual(module.analyze_news("NVDA", []), [])


    def test_bad_json_and_empty_fields(self):
        for payload in ("not-json", '{"issues":[{"headline":"","summary":"ok","tags":[]}]}',
                        '{"issues":[{"headline":"ok","summary":"ok","tags":null}]}'):
            with self.subTest(payload=payload), self.assertRaises((ValueError, json.JSONDecodeError)):
                module.parse_issues(payload)

    def test_groq_request_mocked(self):
        from unittest.mock import patch
        import io
        captured = {}
        class FakeResponse:
            def __enter__(self):
                return io.BytesIO(json.dumps({"choices": [{"message": {"content":
                    '{"issues":[{"headline":"테스트","summary":"내용","tags":["#뉴스"]}]}'}}]}).encode())
            def __exit__(self, *args):
                return False
        def fake_urlopen(request, timeout):
            captured["request"] = json.loads(request.data.decode())
            captured["timeout"] = timeout
            return FakeResponse()
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-only"}), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            result = module.analyze_news("NVDA", [{"title": "기사", "description": "내용"}])
        self.assertEqual(len(result), 1)
        self.assertEqual(captured["request"]["model"], module.MODEL)
        self.assertEqual(captured["request"]["messages"][0]["content"], module.PROMPT)
        self.assertEqual(captured["request"]["response_format"]["type"], "json_object")

    def test_no_api_key_refuses_call(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"GROQ_API_KEY": ""}), patch(
            "urllib.request.urlopen"
        ) as fake:
            with self.assertRaises(RuntimeError):
                module.analyze_news("NVDA", [{"title": "기사"}])
            fake.assert_not_called()


    def test_rejects_missing_article_contents_without_network(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-only"}), patch(
            "urllib.request.urlopen"
        ) as fake:
            self.assertEqual(module.analyze_news("NVDA", [{"title": "제목"}, {"description": "내용"}, None]), [])
            fake.assert_not_called()

    def test_news_payload_has_size_limit(self):
        from unittest.mock import patch
        import io
        captured = {}
        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data)
            return io.BytesIO(b'{"choices":[{"message":{"content":"{\\"issues\\":[]}"}}]}')
        articles = [{"title": f"article {i}", "description": "가" * 2400} for i in range(30)]
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-only"}), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            self.assertEqual(module.analyze_news("NVDA", articles), [])
        body = json.loads(captured["payload"]["messages"][1]["content"])
        self.assertLessEqual(sum(len(x["content"]) for x in body["news"]), 9000)
        self.assertLessEqual(len(body["news"]), 20)

    def test_network_failure_propagates_for_caller_to_handle(self):
        from unittest.mock import patch
        import urllib.error
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-only"}), patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("offline")
        ):
            with self.assertRaises(urllib.error.URLError):
                module.analyze_news("NVDA", [{"title": "기사", "description": "본문"}])

    def test_naver_api_title_description_to_ai_payload(self):
        """Naver API field names should reach AI without Neon column renaming."""
        from unittest.mock import patch
        import io
        captured = {}
        def fake_urlopen(request, timeout):
            captured["request"] = json.loads(request.data.decode("utf-8"))
            return io.BytesIO(b'{"choices":[{"message":{"content":"{\\"issues\\":[]}"}}]}')
        articles = [{"title": "네이버 뉴스 제목", "description": "네이버 뉴스 내용",
                     "pubDate": "Sat, 17 Oct 2026 09:00:00 +0900"}]
        with patch.dict("os.environ", {"GROQ_API_KEY": "offline-only"}), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            self.assertEqual(module.analyze_news("NVDA", articles), [])
        payload = json.loads(captured["request"]["messages"][1]["content"])
        self.assertEqual(payload["news"][0]["title"], articles[0]["title"])
        self.assertEqual(payload["news"][0]["content"], articles[0]["description"])
        self.assertEqual(payload["news"][0]["published_at"], articles[0]["pubDate"])

    def test_naver_api_missing_description_does_not_call_ai(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {"GROQ_API_KEY": "offline-only"}), patch(
            "urllib.request.urlopen"
        ) as api:
            self.assertEqual(module.analyze_news("NVDA", [{"title": "제목", "description": ""}]), [])
            api.assert_not_called()

if __name__ == "__main__":
    unittest.main()
