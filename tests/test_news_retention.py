"""Retention tests: never purge pending or not-yet-preserved news."""
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from backend.database import news_retention


class NewsRetentionTests(unittest.TestCase):
    def test_cleanup_disabled_by_default(self):
        with patch.dict(os.environ, {"NEWS_RAW_CLEANUP_ENABLED": "0",
                                      "NEWS_DATABASE_URL": "postgresql://test"}):
            self.assertEqual(news_retention.purge_expired_processed_news(), 0)

    def test_sql_requires_both_processing_and_expiry(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [(3,), (5,)]
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        dummy_psycopg = types.SimpleNamespace(connect=MagicMock(return_value=connection))
        with patch.dict(os.environ, {"NEWS_RAW_CLEANUP_ENABLED": "1",
                                      "NEWS_DATABASE_URL": "postgresql://test"}):
            with patch.dict(sys.modules, {"psycopg": dummy_psycopg}):
                count = news_retention.purge_expired_processed_news(batch_size=25)
        self.assertEqual(count, 2)
        sql, args = cursor.execute.call_args.args
        self.assertIn("retention_expires_at <= now()", sql)
        self.assertIn("processing_status='processed'", sql)
        self.assertIn("processed_at IS NOT NULL", sql)
        self.assertIn("FOR UPDATE SKIP LOCKED", sql)
        self.assertEqual(args, (25,))

