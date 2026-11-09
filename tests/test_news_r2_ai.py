"""R2 AI output contract: disabled by default, daily reservations, and sourced briefs."""
import datetime as dt
import json
import os
import unittest
from unittest.mock import patch

from backend.services import news_r2_ai


NOW = dt.datetime(2026, 11, 9, 16, 0, tzinfo=dt.timezone.utc)
RAW = [{
    "title": "NVIDIA reports stronger earnings",
    "description": "Revenue increased in the quarter",
    "link": "https://example.org/nvda-earnings",
    "pubDate": "Mon, 09 Nov 2026 15:00:00 GMT",
    "source": "Example News",
}]
ANALYSIS = {"issues": [{
    "headline": "실적 성장",
    "summary": "매출이 증가했다.",
    "tags": ["실적", "성장"],
    "source_ids": [1],
}]}
ENABLED = {
    "GAEMIGTP_NEWS_STORAGE": "r2",
    "GAEMIGTP_NEWS_AI_PAUSED": "0",
    "GAEMIGTP_NEWS_AI_R2_ENABLED": "1",
    "GROQ_API_KEY": "unit-test-placeholder",
}


class AiR2WorkerTests(unittest.TestCase):
    def test_disabled_by_default_even_with_a_groq_key(self):
        with patch.dict(os.environ, {
            "GAEMIGTP_NEWS_STORAGE": "r2",
            "GAEMIGTP_NEWS_AI_PAUSED": "1",
            "GAEMIGTP_NEWS_AI_R2_ENABLED": "0",
            "GROQ_API_KEY": "unit-test-placeholder",
        }):
            self.assertEqual(news_r2_ai.maybe_publish(
                "NVIDIA", "NVDA", RAW, {}, lambda state: None, now=NOW,
                analyzer=lambda *args: self.fail("must not call paid AI"),
            ), "paused")

    def test_one_reservation_before_ai_call_and_no_repeat(self):
        state, saved, uploaded = {}, [], []
        def persist(current):
            saved.append(json.loads(json.dumps(current)))
        def analyze(stock, rows):
            self.assertEqual(
                saved[-1]["_r2_ai_reservations"]["US:NVDA:2026-11-09"],
                "reserved",
            )
            return ANALYSIS
        def upload(path, *, object_key):
            uploaded.append((object_key, json.loads(path.read_text(encoding="utf-8"))))
            return True

        with patch.dict(os.environ, ENABLED):
            self.assertEqual(news_r2_ai.maybe_publish(
                "NVIDIA", "NVDA", RAW, state, persist,
                now=NOW, analyzer=analyze, uploader=upload,
            ), "published")
            self.assertEqual(news_r2_ai.maybe_publish(
                "NVIDIA", "NVDA", RAW, state, persist,
                now=NOW, analyzer=lambda *args: self.fail("duplicate call"),
                uploader=upload,
            ), "already_reserved")
        self.assertEqual(len(uploaded), 1)
        self.assertEqual(uploaded[0][0], "news/ai/us/NVDA.json")
        self.assertEqual(uploaded[0][1]["issue_briefs"][0]["summary"], "매출이 증가했다.")
        self.assertEqual(
            uploaded[0][1]["issue_briefs"][0]["source_articles"][0]["url"],
            "https://example.org/nvda-earnings",
        )
        self.assertIsNone(uploaded[0][1]["price_reason"])
        self.assertEqual(state["_r2_ai_reservations"]["US:NVDA:2026-11-09"], "published")

    def test_failed_paid_call_is_not_retried(self):
        state = {}
        with patch.dict(os.environ, ENABLED):
            result = news_r2_ai.maybe_publish(
                "NVIDIA", "NVDA", RAW, state, lambda x: None, now=NOW,
                analyzer=lambda *a: (_ for _ in ()).throw(RuntimeError("simulated")),
            )
            self.assertEqual(result, "failed")
            self.assertEqual(news_r2_ai.maybe_publish(
                "NVIDIA", "NVDA", RAW, state, lambda x: None, now=NOW,
                analyzer=lambda *args: self.fail("must not retry"),
            ), "already_reserved")

    def test_slot_and_weekend_are_not_billed(self):
        self.assertIsNone(news_r2_ai.us_exchange_day_if_due(
            dt.datetime(2026, 11, 9, 14, 0, tzinfo=dt.timezone.utc)))
        self.assertIsNone(news_r2_ai.us_exchange_day_if_due(
            dt.datetime(2026, 11, 7, 18, 0, tzinfo=dt.timezone.utc)))

    def test_no_articles_do_not_reserve(self):
        state = {}
        with patch.dict(os.environ, ENABLED):
            self.assertEqual(news_r2_ai.maybe_publish(
                "NVIDIA", "NVDA", [], state, lambda x: None, now=NOW,
            ), "no_eligible_articles")
        self.assertNotIn("_r2_ai_reservations", state)

    def test_old_article_never_triggers_paid_call(self):
        stale = [{
            "title": "Old earnings story",
            "description": "Old quarter revenue",
            "link": "https://example.org/old",
            "pubDate": "Fri, 06 Nov 2026 09:00:00 GMT",
        }]
        state = {}
        with patch.dict(os.environ, ENABLED):
            self.assertEqual(news_r2_ai.maybe_publish(
                "NVIDIA", "NVDA", stale, state, lambda x: None, now=NOW,
                analyzer=lambda *args: self.fail("stale article must not be billed"),
            ), "no_eligible_articles")
        self.assertNotIn("_r2_ai_reservations", state)

    def test_reject_unsafe_symbol(self):
        with self.assertRaisesRegex(ValueError, "invalid_us_stock_symbol"):
            news_r2_ai.publish_payload({"symbol": "../latest.json"})


if __name__ == "__main__":
    unittest.main()
