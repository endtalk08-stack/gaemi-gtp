import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from backend.database.news_ai_store import fail_issue_call


class NewsAIFailureStoreTests(unittest.TestCase):
    def _captured_sql(self, category, reason):
        connection = MagicMock()
        conn = connection.__enter__.return_value
        fake = types.SimpleNamespace(connect=MagicMock(return_value=connection))
        with patch.dict(os.environ, {"NEWS_DATABASE_URL": "postgresql://testing"}):
            with patch.dict(sys.modules, {"psycopg": fake}):
                fail_issue_call("KR", "SK하이닉스", "2026-10-15", "hash", category, reason)
        return conn.execute.call_args.args

    def test_json_failure_sets_invalid_status_and_reason(self):
        sql, params = self._captured_sql("json_error", "invalid_json")
        self.assertIn("failure_category=%s", sql)
        self.assertIn("failure_reason=%s", sql)
        self.assertEqual(params[:3], ("invalid", "json_error", "invalid_json"))

    def test_api_failure_consumes_reserved_call(self):
        sql, params = self._captured_sql("api_error", "http_429")
        self.assertIn("status='reserved'", sql)
        self.assertEqual(params[:3], ("failed", "api_error", "http_429"))

    def test_provider_error_text_cannot_enter_database(self):
        _, params = self._captured_sql("api_error", "Bearer SECRET: https://api.example")
        self.assertEqual(params[2], "unspecified")
        self.assertNotIn("SECRET", repr(params))


if __name__ == "__main__":
    unittest.main()
