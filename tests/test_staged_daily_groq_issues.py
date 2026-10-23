"""Offline validation checks for staged Groq issue selection."""
import importlib.util
import json
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "ops" / "staged_daily_groq_issues.py"
spec = importlib.util.spec_from_file_location("staged_daily_groq_issues", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _mock_provider_response(issues):
    analysis = {
        "price_reason": {"headline": "하락 이유", "summary": "뉴스 근거로 하락했어", "source_ids": [1]},
        "issues": issues,
    }
    return json.dumps({"choices": [{"message": {"content": json.dumps(analysis, ensure_ascii=False)}}]},
                      ensure_ascii=False).encode("utf-8")


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
            module.parse_issues('{"issues":[{"headline":"x","summary":"y","tags":[""]}]}')

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
                return io.BytesIO(_mock_provider_response([
                    {"headline": "테스트", "summary": "내용", "tags": ["뉴스"], "source_ids": [1]}
                ]))
            def __exit__(self, *args):
                return False
        def fake_urlopen(request, timeout):
            captured["request"] = json.loads(request.data.decode())
            captured["timeout"] = timeout
            return FakeResponse()
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-only"}), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            result = module.analyze_news("NVDA", [{"title": "기사", "description": "내용", "published_at": "2026-10-17T18:16:00+00:00"}])
        self.assertEqual(len(result["issues"]), 1)
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
            return io.BytesIO(_mock_provider_response([]))
        articles = [{"title": f"article {i}", "description": "가" * 2400} for i in range(30)]
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-only"}), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            self.assertEqual(module.analyze_news("NVDA", articles)["issues"], [])
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
            return io.BytesIO(_mock_provider_response([]))
        articles = [{"title": "네이버 뉴스 제목", "description": "네이버 뉴스 내용",
                     "pubDate": "Sat, 17 Oct 2026 09:00:00 +0900"}]
        with patch.dict("os.environ", {"GROQ_API_KEY": "offline-only"}), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            self.assertEqual(module.analyze_news("NVDA", articles)["issues"], [])
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


    def test_issue_records_for_screen_storage(self):
        from datetime import date
        ai_issues = [
            {"headline": "수요 증가", "summary": "메모리 수요 확대", "tags": ["#수요증가"]},
            {"headline": "매출 증가", "summary": "매출 성장 기대", "tags": ["#매출증가"]},
        ]
        rows = module.issue_records(
            ai_issues, market="KR", symbol="005930", exchange_day=date(2026, 10, 17)
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["headline"] for r in rows], ["수요 증가", "매출 증가"])
        self.assertEqual(rows[0]["tags"], ["#수요증가"])
        self.assertEqual(rows[0]["model_id"], module.MODEL)
        self.assertNotIn("published_at", rows[0])
        self.assertNotIn("generated_at", rows[0])
        self.assertNotIn("article_id", rows[0])

    def test_zero_issues_produces_no_rows(self):
        from datetime import date
        self.assertEqual(
            module.issue_records([], market="US", symbol="NVDA", exchange_day=date(2026, 10, 17)),
            [],
        )

    def test_invalid_four_issues_produces_no_rows(self):
        from datetime import date
        ai_issues = [{"headline": "제목", "summary": "내용", "tags": []} for _ in range(4)]
        with self.assertRaises(ValueError):
            module.issue_records(ai_issues, market="US", symbol="NVDA", exchange_day=date(2026, 10, 17))

    def test_invalid_citation_ids_do_not_abort_other_valid_sources(self):
        candidate = {"headline": "테슬라 생산 발표", "summary": "공장 증설 발표", "tags": [],
                     "source_ids": ["1", 1, "oops", 999, 2, 2]}
        issues = module.parse_issues(json.dumps({"issues": [candidate]}))
        self.assertEqual(issues[0]["source_ids"], [1, 999, 2])
        news = [
            {"source_id": 1, "published_at": "2026-10-20T12:00:00+00:00"},
            {"source_id": 2, "published_at": "2026-10-20T12:05:00+00:00"},
        ]
        checked = module._keep_sourced_issues(issues, news)
        self.assertEqual(len(checked), 1)
        self.assertEqual(checked[0]["source_ids"], [1, 2])

    def test_unverifiable_citation_does_not_create_fake_evidence(self):
        candidate = {"headline": "확인되지 않은 주장", "summary": "근거 없음", "tags": [],
                     "source_ids": [999, "invalid"]}
        issues = module.parse_issues(json.dumps({"issues": [candidate]}))
        news = [{"source_id": 1, "published_at": "2026-10-20T12:00:00+00:00"}]
        self.assertEqual(module._keep_sourced_issues(issues, news), [])

    def test_missing_source_ids_remain_unverified(self):
        candidate = {"headline": "출처 번호 누락", "summary": "근거 불명", "tags": []}
        issues = module.parse_issues(json.dumps({"issues": [candidate]}))
        news = [{"source_id": 1, "published_at": "2026-10-20T12:00:00+00:00"}]
        self.assertEqual(module._keep_sourced_issues(issues, news), [])

    def test_malformed_nonlist_source_ids_do_not_abort_batch(self):
        candidate = {"headline": "숫자형 오류", "summary": "구조 오류", "tags": [],
                     "source_ids": {"bad": True}}
        issues = module.parse_issues(json.dumps({"issues": [candidate]}))
        self.assertEqual(issues[0]["source_ids"], [])

    def test_prompt_matches_user_requested_exact_text(self):
        expected = """제공된 종목의 현재 주가와 뉴스 원문을 분석해서 친구처럼 반말로 답변해.

1. 현재 주가가 상승했으면 왜 상승했어?
   현재 주가가 하락했으면 왜 하락했어?

2. 현재 해당 종목에서 중요한 이슈를 0~3개 선정해.

각 이슈의 태그는 최대 3개이고 # 기호 없이 작성해.
한국어 JSON 객체만 반환해:
{"price_reason":{"headline":"상승 또는 하락 이유 제목","summary":"상승 또는 하락한 이유","source_ids":[1]},"issues":[{"headline":"이슈 제목","summary":"이슈 내용","tags":["키워드1"],"source_ids":[1]}]}"""
        self.assertEqual(module.PROMPT, expected)

    def test_old_event_dates_are_tagged_using_article_publication_time(self):
        article = {
            "title": "마이크론, 로봇용 메모리 개발",
            "description": "SK하이닉스는 6월 8일 엔비디아와 장기 협력을 발표했다. 지난 8월 다른 공급 협력도 체결했다.",
            "published_at": "2026-10-19T18:40:00+00:00",
        }
        news, sources = module.build_model_news([article])
        self.assertEqual(news[0]["historical_event_mentions"], ["6월 8일", "지난 8월"])
        self.assertEqual(news[0]["source_id"], sources[0]["source_id"])
        self.assertEqual(news[0]["published_at"], article["published_at"])

    def test_current_event_is_not_mislabeled_as_historical(self):
        articles = [{
            "title": "실적 발표", "description": "10월 19일 3분기 실적을 발표했다.",
            "published_at": "2026-10-19T18:40:00+00:00",
        }, {
            "title": "신제품 공개", "description": "10월 18일 신규 제품을 공개했다.",
            "published_at": "2026-10-19T18:40:00+00:00",
        }]
        news, _ = module.build_model_news(articles)
        self.assertEqual([r["historical_event_mentions"] for r in news], [[], []])

    def test_prior_year_explicit_and_impossible_dates(self):
        text = "2025년 12월 3일 투자 발표. 2026년 2월 30일은 유효한 날짜가 아니다."
        self.assertEqual(module._historical_event_mentions(text, "2026-10-19T18:40:00+00:00"), ["2025년 12월 3일"])
        self.assertEqual(module._historical_event_mentions("6월 8일 발표", ""), [])

    def test_model_request_sends_historical_hints_without_second_ai_call(self):
        import io
        from unittest.mock import patch
        captured = {}
        article = {"title": "마이크론 로봇용 메모리 개발",
                   "description": "SK하이닉스는 6월 8일 엔비디아와 장기 협력을 발표했다.",
                   "published_at": "2026-10-19T18:40:00+00:00"}
        def mock_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return io.BytesIO(_mock_provider_response([]))
        with patch.dict("os.environ", {"GROQ_API_KEY": "mock-only"}), patch(
            "urllib.request.urlopen", side_effect=mock_urlopen
        ) as provider:
            self.assertEqual(module.analyze_news("엔비디아", [article])["issues"], [])
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(captured["payload"]["messages"][0]["content"], module.PROMPT)
        model_news = json.loads(captured["payload"]["messages"][1]["content"])["news"]
        self.assertEqual(model_news[0]["historical_event_mentions"], ["6월 8일"])
        self.assertEqual(model_news[0]["source_id"], 1)

    def test_truncated_response_fails_without_retry_or_fabrication(self):
        import io
        from unittest.mock import patch
        from unittest.mock import Mock
        payload = {"choices": [{"finish_reason": "length",
                                "message": {"content": '{"issues":['}}]}
        api = Mock(return_value=io.BytesIO(json.dumps(payload).encode()))
        with patch.dict("os.environ", {"GROQ_API_KEY": "mock"}), patch(
            "urllib.request.urlopen", api
        ):
            with self.assertRaisesRegex(ValueError, "model_response_truncated"):
                module.analyze_news("NVDA", [
                    {"title": "News", "description": "Evidence",
                     "published_at": "2026-10-18T10:00:00+00:00"}
                ])
        api.assert_called_once()

    def test_empty_model_response_does_not_count_as_no_issues(self):
        import io
        from unittest.mock import patch
        payload = {"choices": [{"finish_reason": "stop",
                                "message": {"content": ""}}]}
        with patch.dict("os.environ", {"GROQ_API_KEY": "mock"}), patch(
            "urllib.request.urlopen",
            return_value=io.BytesIO(json.dumps(payload).encode())
        ):
            with self.assertRaisesRegex(ValueError, "model_response_empty"):
                module.analyze_news("NVDA", [
                    {"title": "News", "description": "Evidence",
                     "published_at": "2026-10-18T10:00:00+00:00"}
                ])


if __name__ == "__main__":
    unittest.main()
