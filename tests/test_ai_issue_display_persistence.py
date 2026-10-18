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
            ("테슬라", "FSD 도입", "검증된 기사", ["FSD"], old)
        ]
        module = types.SimpleNamespace(connect=lambda *args, **kwargs: connection)
        with patch.dict(os.environ, {"NEWS_DATABASE_URL": "postgresql://test"}), \
             patch.dict(sys.modules, {"psycopg": module}):
            data = ai_issue_display_store.read_ai_issue_briefs("미국", ["테슬라"])

        self.assertEqual(data["테슬라"][0]["headline"], "FSD 도입")
        self.assertEqual(data["테슬라"][0]["source"], "ai_issue")
        self.assertEqual(data["테슬라"][0]["generated_at"], old.isoformat())
        sql = cursor.execute.call_args.args[0]
        self.assertIn("MAX(exchange_day)", sql)
        self.assertNotIn("interval '24 hours'", sql)

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
