"""R2-only US stock news transport must not touch the Neon store or news page."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import news_worker
from backend.services import r2_news_uploader


class R2StockNewsWorkerTests(unittest.TestCase):
    def test_r2_publication_is_separate_from_news_page_and_neon(self):
        state = {}
        captured = {}
        article = {
            "title": "Company announces results",
            "description": "Revenue increased",
            "link": "https://example.org/report",
            "pubDate": "Mon, 09 Nov 2026 08:00:00 GMT",
            "_code_issue_briefs": [{"headline": "should not publish"}],
        }

        def fake_upload(path, *, object_key):
            captured["object_key"] = object_key
            captured["payload"] = json.loads(Path(path).read_text(encoding="utf-8"))
            return True

        with patch.object(news_worker.news_feed, "fetch_stock_news", return_value=[article]), \
             patch.object(news_worker.store, "source_fingerprint", return_value="news-sha"), \
             patch.object(news_worker.store, "save_snapshot", side_effect=AssertionError("Neon write")), \
             patch.object(r2_news_uploader, "upload_file", side_effect=fake_upload) as upload:
            self.assertEqual(news_worker.process_r2_stock("미국", "NVIDIA", "NVDA", state), "updated")
            self.assertEqual(news_worker.process_r2_stock("미국", "NVIDIA", "NVDA", state), "unchanged")

        self.assertEqual(upload.call_count, 1)
        self.assertEqual(captured["object_key"], "news/stocks/us/NVDA.json")
        self.assertNotEqual(captured["object_key"], "news/latest.json")
        self.assertEqual(captured["payload"]["symbol"], "NVDA")
        self.assertEqual(captured["payload"]["count"], 1)
        self.assertNotIn("_code_issue_briefs", captured["payload"]["items"][0])
        self.assertNotIn("issue_briefs", captured["payload"]["items"][0])
        self.assertNotIn("_ai_issue_briefs", captured["payload"]["items"][0])

    def test_failed_upload_does_not_mark_news_as_published(self):
        state = {}
        with patch.object(news_worker.news_feed, "fetch_stock_news", return_value=[
            {"title": "New report", "link": "https://example.org/a"}
        ]), patch.object(news_worker.store, "source_fingerprint", return_value="sha"), \
             patch.object(r2_news_uploader, "upload_file", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "r2_news_upload_failed"):
                news_worker.process_r2_stock("미국", "NVIDIA", "NVDA", state)
        self.assertNotIn("NVDA", state.get("_r2_news_fingerprints", {}))

    def test_empty_feed_preserves_previous_publication(self):
        state = {"_r2_news_fingerprints": {"NVDA": "previous"}}
        with patch.object(news_worker.news_feed, "fetch_stock_news", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "empty news source"):
                news_worker.process_r2_stock("미국", "NVIDIA", "NVDA", state)
        self.assertEqual(state["_r2_news_fingerprints"]["NVDA"], "previous")

    def test_invalid_symbol_does_not_publish(self):
        with self.assertRaisesRegex(ValueError, "invalid_us_stock_symbol"):
            news_worker.process_r2_stock("미국", "NVIDIA", "../news/latest", {})

    def test_existing_uploader_key_is_backwards_compatible(self):
        with self.assertRaisesRegex(ValueError, "invalid_r2_news_object_key"):
            r2_news_uploader.upload_file(Path("unused.json"), object_key="../news/latest.json")
        self.assertEqual(r2_news_uploader.OBJECT_KEY, "news/latest.json")

    def test_storage_selection_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(news_worker.news_storage_mode(), "neon")
        with patch.dict(os.environ, {"GAEMIGTP_NEWS_STORAGE": "r2"}):
            self.assertEqual(news_worker.news_storage_mode(), "r2")


if __name__ == "__main__":
    unittest.main()
