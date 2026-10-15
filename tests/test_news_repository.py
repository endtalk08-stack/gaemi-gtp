import os
import unittest
from unittest.mock import patch
from backend.database import news_repository as store

class NewsRepositoryTests(unittest.TestCase):
    def test_disabled_does_not_enqueue(self):
        with patch.dict(os.environ, {"NEWS_METADATA_STORAGE_ENABLED": "0", "NEWS_DATABASE_URL": "postgres://test"}):
            with patch.object(store._QUEUE, "put_nowait") as enqueue:
                store.enqueue_news_metadata("SK하이닉스", "국내", [{"title": "test"}])
                enqueue.assert_not_called()

    def test_source_types_are_separate(self):
        self.assertEqual(store._source({"url": "https://example.com/a"})[2], "news")
        self.assertEqual(store._source({"url": "https://example.com/a", "source_type": "sec_filing"})[2], "filing")
        self.assertEqual(store._source({"url": "https://example.com/a", "source_type": "official_company"})[2], "company")

if __name__ == "__main__":
    unittest.main()
