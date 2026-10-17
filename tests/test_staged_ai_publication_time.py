"""Offline checks for real article timestamps and truthful source links."""
import pathlib
import sys
import unittest
from datetime import date
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops"))
from staged_daily_groq_issues import issue_source_metadata, parse_issues
from staged_ai_snapshot_integration import with_ai_issue_briefs
from staged_ai_sequential_batch import run_stock_batch


class PublicationTimeTests(unittest.TestCase):
    def setUp(self):
        self.articles = [
            {"title": "제목만 있는 기사"},
            {"title": "반도체 기사", "description": "채권 부담",
             "published_at": "2026-10-17T18:16:00+00:00",
             "source": "g-enews.com", "url": "https://example.org/one"},
            {"title": "추가 기사", "description": "후속 기사",
             "pubDate": "Sat, 17 Oct 2026 21:05:00 +0900",
             "source": "후속매체", "link": "https://example.org/two"},
        ]
        self.issues = [{"headline": "AI 부채", "summary": "회사채 부담",
                        "tags": ["#AI부채"], "source_ids": [1, 2]}]

    def test_mapping_only_usable_articles(self):
        sources = issue_source_metadata(self.issues, self.articles)
        self.assertEqual([s["title"] for s in sources[0]], ["반도체 기사", "추가 기사"])

    def test_publication_time_and_analysis_time_separate(self):
        sources = issue_source_metadata(self.issues, self.articles)
        updated = with_ai_issue_briefs(
            {"paired_news_items": self.articles}, self.issues,
            display_time="2026-10-18 04:48", stock_names=["브로드컴"],
            sources_by_issue=sources)
        brief = updated["issue_briefs"][0]
        self.assertEqual(brief["time"], "03:16")
        self.assertNotIn("기사 발행", brief["time"])
        self.assertNotIn("AI 분석", brief["time"])
        self.assertNotIn("g-enews.com", brief["time"])
        self.assertEqual(brief["source_articles"][0]["source"], "g-enews.com")
        self.assertEqual(brief["source_articles"][0]["url"], "https://example.org/one")
        self.assertEqual(len(brief["source_articles"]), 2)
        self.assertEqual(updated["paired_news_items"], self.articles)

    def test_missing_source_does_not_invent_news_time(self):
        issue = [{"headline":"소식", "summary":"내용", "tags":[]}]
        updated = with_ai_issue_briefs({}, issue, display_time="04:48",
                                      stock_names=["메타"], sources_by_issue=[[]])
        self.assertEqual(updated["issue_briefs"][0]["time"], "04:48")

    def test_invalid_indices_never_lookup_unrelated_article(self):
        issue = [{"headline":"소식", "summary":"내용", "tags":[], "source_ids":[999]}]
        self.assertEqual(issue_source_metadata(issue, self.articles), [[]])

    def test_validate_article_references(self):
        for bad in ("true", "0", "-1"):
            with self.assertRaises(ValueError):
                parse_issues('{"issues":[{"headline":"x","summary":"y","tags":[],"source_ids":['+bad+']}]}')

    def test_source_ids_are_required_in_actual_model_response(self):
        from unittest.mock import patch
        import io
        import json

        def model_response(issue):
            payload = {"choices": [{"message": {"content": json.dumps(
                {"issues": [issue]}, ensure_ascii=False)}}]}
            return io.BytesIO(json.dumps(payload).encode("utf-8"))

        base = {"headline": "뉴스 이슈", "summary": "검증",
                "tags": ["#AI"]}
        cases = [
            ({**base}, 0),
            ({**base, "source_ids": [99]}, 0),
            ({**base, "source_ids": [1]}, 1),
            ({**base, "source_ids": [2]}, 1),
        ]
        for response_issue, expected_count in cases:
            with self.subTest(response=response_issue):
                with patch.dict("os.environ", {"GROQ_API_KEY": "mock-only"}), patch(
                    "urllib.request.urlopen",
                    return_value=model_response(response_issue)
                ) as api:
                    from staged_daily_groq_issues import analyze_news
                    output = analyze_news("브로드컴", self.articles)
                    self.assertEqual(len(output), expected_count)
                    api.assert_called_once()

    def test_source_date_requires_explicit_timezone(self):
        from staged_daily_groq_issues import _has_verifiable_published_at
        self.assertTrue(_has_verifiable_published_at("2026-10-17T18:16:00+00:00"))
        self.assertTrue(_has_verifiable_published_at("Sat, 17 Oct 2026 09:00:00 +0900"))
        self.assertFalse(_has_verifiable_published_at(""))
        self.assertFalse(_has_verifiable_published_at("2026-10-17 18:16:00"))
        self.assertFalse(_has_verifiable_published_at("not-a-date"))

    def test_news_without_pubtime_does_not_get_article_time(self):
        from staged_daily_groq_issues import _keep_sourced_issues, build_model_news
        news, _ = build_model_news([{"title":"뉴스", "description":"본문"}])
        issue = {"headline":"AI", "summary":"본문", "tags":[],
                 "source_ids":[1]}
        self.assertEqual(_keep_sourced_issues([issue], news), [])

    def test_article_metadata_is_passed_for_atomic_storage(self):
        data=[]
        class Tx:
            def __enter__(self): return self
            def __exit__(self, *args): return False
        class Conn:
            def transaction(self): return Tx()
        captured=[]
        def save(*args, **kwargs):
            captured.extend(kwargs["sources_by_issue"])
            return [88]
        result=run_stock_batch(Conn(), [{
            "name":"브로드컴", "articles":self.articles, "market":"US",
            "symbol":"브로드컴", "exchange_day":date(2026,10,17)
        }], analyze=lambda *args:self.issues,
            save=save,
            reserve=lambda *args,**kwargs:True,
            finish=lambda *args,**kwargs:data.append(kwargs["result"]))[0]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(data[0]["issue_ids"], [88])
        self.assertEqual(captured[0][0]["published_at"],
                         "2026-10-17T18:16:00+00:00")
        self.assertEqual(captured[0][0]["description"], "채권 부담")
        self.assertNotIn("issue_sources", data[0])


if __name__ == "__main__":
    unittest.main()
