"""Offline regressions for fresh article sources and real Groq token accounting."""
import io
import json
import pathlib
import sys
import unittest
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, Mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops"))
from staged_daily_groq_issues import recent_ai_articles, _safe_token_usage
from staged_ai_sequential_batch import has_eligible_ai_news, run_stock_batch
from staged_news_processed_store import _fresh_ai_briefs, _prefer_same_day_ai


def published(hours=0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


class FreshIssueTokenTests(unittest.TestCase):
    def test_recent_article_input_only_and_expired_does_not_call_ai(self):
        old = {"title": "old", "description": "old data", "published_at": published(49)}
        recent = {"title": "new", "description": "recent data", "published_at": published(1)}
        future = {"title": "future", "description": "invalid", "published_at": published(-2)}
        self.assertEqual(recent_ai_articles([old, recent, future]), [recent])
        self.assertTrue(has_eligible_ai_news([old, recent]))
        self.assertFalse(has_eligible_ai_news([old, future]))

    def test_ai_briefs_expire_by_article_time_not_snapshot_time(self):
        old = {"headline": "OLD", "stock_names": ["테슬라"],
               "source_articles": [{"published_at": published(49), "source": "press",
                                    "url": "https://example.org/old"}]}
        fresh = {"headline": "NEW", "stock_names": ["테슬라"],
                 "source_articles": [{"published_at": published(1), "source": "press",
                                      "url": "https://example.org/new"},
                                     {"published_at": published(49), "source": "press",
                                      "url": "https://example.org/old"}]}
        filtered = _fresh_ai_briefs([old, fresh])
        self.assertEqual([x["headline"] for x in filtered], ["NEW"])
        self.assertEqual(len(filtered[0]["source_articles"]), 1)
        self.assertNotIn("analysis", filtered[0]["time"].lower())

    def test_code_brief_never_reappears_when_ai_expires(self):
        old = {"_ai_exchange_day": "2026-10-18",
               "_ai_issue_briefs": [{"headline": "OLD", "stock_names": ["테슬라"],
                                      "source_articles": [{"published_at": published(49),
                                          "source": "press", "url": "https://example.org/old"}]}]}
        incoming = {"issue_briefs": [{"headline": "CODE", "stock_names": ["테슬라"]}]}
        result = _prefer_same_day_ai(incoming, old, "테슬라", "2026-10-18")
        self.assertEqual(result["issue_briefs"], [])
        self.assertEqual(result["_code_issue_briefs"][0]["headline"], "CODE")
        self.assertNotIn("_ai_issue_briefs", result)

    def test_provider_usage_safe_and_not_estimated(self):
        self.assertEqual(_safe_token_usage({"usage": {"prompt_tokens": 321,
                        "completion_tokens": 789, "total_tokens": 1110,
                        "completion_tokens_details": {"reasoning_tokens": 300},
                        "secret": "ignored"}}),
                         {"prompt_tokens": 321, "completion_tokens": 789,
                          "total_tokens": 1110, "reasoning_tokens": 300})
        self.assertEqual(_safe_token_usage({"usage": {}}), {})

    def test_success_usage_saved_in_existing_ledger_result_without_real_api(self):
        article = {"title": "news", "description": "body",
                   "published_at": published(1), "url": "https://example.org/one"}
        provider_response = {
            "choices": [{"message": {"content": '{"issues":[]}'}}],
            "usage": {"prompt_tokens": 432, "completion_tokens": 25, "total_tokens": 457},
        }
        completed = []
        class Connection:
            def transaction(self):
                return nullcontext()
        def finish(*args, **kwargs):
            completed.append(kwargs)
            return True
        with patch.dict("os.environ", {"GROQ_API_KEY": "mock-only"}), patch(
                "urllib.request.urlopen",
                side_effect=lambda *a, **kw: io.BytesIO(json.dumps(provider_response).encode())) as api:
            result = run_stock_batch(Connection(), [{
                "name": "테슬라", "symbol": "테슬라", "market": "US",
                "exchange_day": date(2026, 10, 18), "articles": [article]
            }], reserve=lambda *args, **kwargs: True, finish=finish, save=Mock())[0]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(completed[0]["result"]["usage"],
                         {"prompt_tokens": 432, "completion_tokens": 25, "total_tokens": 457})
        api.assert_called_once()

    def test_invalid_model_output_still_records_reported_usage(self):
        article = {"title": "news", "description": "body", "published_at": published(1)}
        completed = []
        response = {"choices": [{"message": {"content": "invalid json"}}],
                    "usage": {"prompt_tokens": 501, "completion_tokens": 1000,
                              "total_tokens": 1501}}
        with patch.dict("os.environ", {"GROQ_API_KEY": "mock-only"}), patch(
            "urllib.request.urlopen",
            side_effect=lambda *a, **kw: io.BytesIO(json.dumps(response).encode())):
            result = run_stock_batch(type("Conn", (), {"transaction": lambda self: nullcontext()})(), [{
                "name": "테슬라", "symbol": "테슬라", "market": "US",
                "exchange_day": date(2026, 10, 18), "articles": [article]
            }], reserve=lambda *a, **kw: True,
                finish=lambda *a, **kw: completed.append(kw), save=Mock())[0]
        self.assertEqual(result["status"], "error")
        self.assertEqual(completed[0]["result"]["usage"]["total_tokens"], 1501)


if __name__ == "__main__":
    unittest.main()
