"""Offline regression checks for stopped TOP20 worker R2 mode (no network, no Neon)."""
from __future__ import annotations
import os
import sys
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, "/opt/gaemigtp-news/app")

class R2ModeTests(unittest.TestCase):
    def test_r2_publish_and_skip_neon(self):
        from backend import news_worker as w
        sample=[{"title":"NVIDIA contracts", "url":"https://example.invalid/story"}]
        with mock.patch.dict(os.environ, {"GAEMIGTP_NEWS_STORAGE":"r2", "NEWS_DATABASE_URL":"postgresql://should-not-connect"}, clear=False):
            self.assertEqual(w.store.database_url(),"")
            with mock.patch.object(w.news_feed,"fetch_stock_news",return_value=sample),\
                 mock.patch.object(w,"build_stock_news_result",return_value={"_news_status":"ok","paired_news_items":[]}),\
                 mock.patch.object(w.store,"read_signature",side_effect=AssertionError("unexpected Neon")),\
                 mock.patch.object(w.store,"save_snapshot",side_effect=AssertionError("unexpected Neon")),\
                 mock.patch("backend.services.top20_r2_store.upload_bytes",return_value=True) as uploaded:
                self.assertEqual(w.process_stock("미국","엔비디아",symbol="NVDA"),"r2_updated")
                self.assertEqual(uploaded.call_count,1)
                self.assertEqual(uploaded.call_args.kwargs["object_key"],"news/top20/NVDA.json")
                self.assertNotIn(b"postgresql",uploaded.call_args.args[0])
            with mock.patch.object(w,"next_ranked_stock",return_value=None),\
                 mock.patch.object(w.store,"purge_expired",side_effect=AssertionError("unexpected Neon maintenance")),\
                 mock.patch.object(w.store,"purge_expired_original_news",side_effect=AssertionError("unexpected Neon maintenance")):
                self.assertFalse(w.run_once({},maintenance=True))

    def test_invalid_result_never_uploads(self):
        from backend.services.top20_r2_store import publish_stock_news
        with mock.patch("backend.services.top20_r2_store.upload_bytes") as uploader:
            with self.assertRaises(ValueError):
                publish_stock_news("../bad","Test","a"*64,{"_news_status":"ok"})
            with self.assertRaises(ValueError):
                publish_stock_news("NVDA","Test","a"*64,{"_news_status":"failed"})
            uploader.assert_not_called()

    def test_existing_tv_default_key_is_unchanged(self):
        from backend.services import r2_news_uploader as upload
        self.assertEqual(upload.OBJECT_KEY,"news/latest.json")
        with self.assertRaises(ValueError):
            upload.upload_bytes(b"{}",object_key="news/latest-other.json")
        with self.assertRaises(ValueError):
            upload.upload_bytes(b"{}",object_key="news/top20/../latest.json")

    def test_upload_failure_never_marks_success(self):
        from backend import news_worker as w
        with mock.patch.dict(os.environ,{"GAEMIGTP_NEWS_STORAGE":"r2"},clear=False):
            with mock.patch.object(w.news_feed,"fetch_stock_news",return_value=[{"title":"test"}]),\
                 mock.patch.object(w,"build_stock_news_result",return_value={"_news_status":"ok"}),\
                 mock.patch("backend.services.top20_r2_store.upload_bytes",return_value=False):
                with self.assertRaisesRegex(RuntimeError,"r2_upload_failed"):
                    w.process_stock("미국","엔비디아",symbol="NVDA")

if __name__ == "__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(R2ModeTests)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    print("TOP20_R2_OFFLINE_TESTS_PASS="+str(result.wasSuccessful()),flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
