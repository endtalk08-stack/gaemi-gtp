"""Neon AI issue display retention regressions; no external DB or AI calls."""
import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from backend.services import ai_issue_display_store, news_result


class AiIssueDisplayPersistenceTests(unittest.TestCase):
    def test_latest_issue_day_is_read_even_after_raw_news_ttl(self):
        old = datetime.now(timezone.utc) - timedelta(hours=30)
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ("테슬라", "FSD 도입", "검증된 기사", ["FSD"], old,
             "16:42", "2026-10-18T07:42:00+00:00")
        ]
        module = types.SimpleNamespace(connect=lambda *args, **kwargs: connection)
        with patch.dict(os.environ, {"NEWS_DATABASE_URL": "postgresql://test"}), \
             patch.dict(sys.modules, {"psycopg": module}):
            data = ai_issue_display_store.read_ai_issue_briefs("미국", ["테슬라"])

        self.assertEqual(data["테슬라"][0]["headline"], "FSD 도입")
        self.assertEqual(data["테슬라"][0]["source"], "ai_issue")
        self.assertEqual(data["테슬라"][0]["generated_at"], old.isoformat())
        self.assertEqual(data["테슬라"][0]["time"], "16:42")
        self.assertEqual(data["테슬라"][0]["published_at"], "2026-10-18T07:42:00+00:00")
        sql = cursor.execute.call_args.args[0]
        self.assertIn("MAX(exchange_day)", sql)
        self.assertNotIn("interval '24 hours'", sql)
        self.assertIn("news_processed_snapshots", sql)
        self.assertIn("source_articles", sql)
        self.assertIn("b.brief->>'headline'=i.headline", sql)


    def test_no_news_timestamp_does_not_show_ai_generation_clock(self):
        now = datetime(2026, 10, 18, 14, 49, tzinfo=timezone.utc)
        conn = MagicMock()
        cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = [("테슬라", "제목", "본문", [], now, None, None)]
        with patch.dict(os.environ, {"NEWS_DATABASE_URL": "postgresql://test"}), \
             patch.dict(sys.modules, {"psycopg": types.SimpleNamespace(connect=lambda *args, **kw: conn)}):
            issues = ai_issue_display_store.read_ai_issue_briefs("us", ["테슬라"])
        self.assertEqual(issues["테슬라"][0]["time"], "기사시각 미확인")
        self.assertNotEqual(issues["테슬라"][0]["time"], "14:49")

    def test_article_publication_timestamp_fallback_uses_korea_time(self):
        now = datetime(2026, 10, 18, 14, 49, tzinfo=timezone.utc)
        conn = MagicMock()
        cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = [("테슬라", "제목", "본문", [], now, "", "2026-10-18T12:00:00+00:00")]
        with patch.dict(os.environ, {"NEWS_DATABASE_URL": "postgresql://test"}), \
             patch.dict(sys.modules, {"psycopg": types.SimpleNamespace(connect=lambda *args, **kw: conn)}):
            issues = ai_issue_display_store.read_ai_issue_briefs("us", ["테슬라"])
        self.assertEqual(issues["테슬라"][0]["time"], "21:00")

    def test_database_error_is_distinct_from_no_saved_issues(self):
        module = types.SimpleNamespace(connect=lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))
        with patch.dict(os.environ, {"NEWS_DATABASE_URL": "postgresql://test"}), \
             patch.dict(sys.modules, {"psycopg": module}):
            self.assertIsNone(ai_issue_display_store.read_ai_issue_briefs("us", ["테슬라"]))

    def test_transient_error_does_not_replace_existing_ai_brief_with_heuristic(self):
        worker = {
            "issue_briefs": [
                {"headline": "저장된 AI", "summary": "기존", "source": "ai_issue"},
                {"headline": "단순 키워드", "source": "heuristic"},
            ]
        }
        with patch.object(news_result, "_read_worker_news_snapshot", return_value=worker), \
             patch.object(news_result, "read_ai_issue_briefs", return_value=None):
            data = news_result.get_shared_stock_news_result("테슬라", market="미국")
        self.assertEqual([row["headline"] for row in data["issue_briefs"]], ["저장된 AI"])


if __name__ == "__main__":
    unittest.main()
