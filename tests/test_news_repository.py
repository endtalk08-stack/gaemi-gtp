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

    def test_article_id_query_is_not_lost_when_tracking_removed(self):
        from backend.database.news_url import canonical_news_url, news_url_hash
        one = "https://news.naver.com/main/read.naver?oid=001&aid=111&utm_source=feed"
        two = "https://news.naver.com/main/read.naver?aid=222&oid=001"
        one_without_tracking = "https://news.naver.com/main/read.naver?aid=111&oid=001"
        self.assertEqual(news_url_hash(one), news_url_hash(one_without_tracking))
        self.assertNotEqual(news_url_hash(one), news_url_hash(two))
        self.assertIn("aid=111", canonical_news_url(one))

    def test_source_types_are_separate(self):
        self.assertEqual(store._source({"url": "https://example.com/a"})[2], "news")
        self.assertEqual(store._source({"url": "https://example.com/a", "source_type": "sec_filing"})[2], "filing")
        self.assertEqual(store._source({"url": "https://example.com/a", "source_type": "official_company"})[2], "company")

if __name__ == "__main__":
    unittest.main()
