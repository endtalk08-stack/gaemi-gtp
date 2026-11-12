"""Offline regression tests: paid news text must survive feed refreshes.

No external API, R2 operation or running service is contacted.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.services import tradingview_news_page as news
from backend import tradingview_news_worker as worker
from backend.services import r2_news_uploader as r2


def article(article_id="a", *, text=True):
    row = {
        "id": article_id,
        "title": "엔비디아 4분기 실적 발표",
        "published": 1794520000,
        "news_category": "overall",
        "news_categories": ["overall"],
        "relatedSymbols": [{"symbol": "NASDAQ:NVDA"}],
        "permission": "headline",
    }
    if text:
        row.update({
            "detail_body": "확인된 기사 본문. 실제 매출이 증가했다.",
            "detail_summary": "확인된 유료 API 요약",
            "detail_checked": "content",
            "detail_publication_allowed": True,
            "detail_rights_confirmed": True,
        })
    return row


class PaidNewsPreservationTests(unittest.TestCase):
    def test_article_id_keeps_old_text_after_headline_only_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "news.json"
            first = news.write_snapshot([article()], path=file)
            self.assertEqual(first["items"][0]["summary"], "확인된 유료 API 요약")
            self.assertTrue(first["items"][0]["body_available"])
            again = news.write_snapshot([article(text=False)], path=file)
            self.assertEqual(again["items"][0]["body"], first["items"][0]["body"])
            self.assertEqual(again["items"][0]["summary"], first["items"][0]["summary"])
            self.assertEqual(again["items"][0]["list_excerpt"], first["items"][0]["list_excerpt"])
            self.assertTrue(again["items"][0]["body_available"])
            self.assertEqual(again["generated_at"], first["generated_at"])
            self.assertEqual(json.loads(file.read_text())["items"][0]["body"], first["items"][0]["body"])

    def test_same_title_new_id_does_not_inherit_unrelated_article_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "news.json"
            news.write_snapshot([article("old")], path=file)
            result = news.write_snapshot([article("different", text=False)], path=file)
            self.assertEqual(result["items"][0]["id"], "different")
            self.assertEqual(result["items"][0]["body"], "")
            self.assertEqual(result["items"][0]["summary"], "")

    def test_invalid_previous_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "news.json"
            file.write_text('{"items":"invalid"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                news.write_snapshot([article()], path=file)
            self.assertEqual(file.read_text(), '{"items":"invalid"}')

    def test_archive_saved_before_next_write_and_failure_blocks_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "news.json"
            news.write_snapshot([article()], path=file)
            original = file.read_bytes()
            with mock.patch.object(worker, "NEWS_PAGE_PATH", file), \
                 mock.patch.object(worker, "_archived_file_hashes", set()), \
                 mock.patch.object(worker, "upload_file", return_value=False) as upload:
                with self.assertRaises(RuntimeError):
                    worker.archive_existing_news_snapshot()
                self.assertEqual(file.read_bytes(), original)
                key = upload.call_args.kwargs["object_key"]
                self.assertRegex(key, r"^news/archive/\d{8}/[0-9a-f]{64}\.json$")
                self.assertEqual(key.split("/")[-1], hashlib.sha256(original).hexdigest() + ".json")

    def test_archiving_same_file_twice_does_not_repeat_r2_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "news.json"
            news.write_snapshot([article()], path=file)
            with mock.patch.object(worker, "NEWS_PAGE_PATH", file), \
                 mock.patch.object(worker, "_archived_file_hashes", set()), \
                 mock.patch.object(worker, "upload_file", return_value=True) as upload:
                worker.archive_existing_news_snapshot()
                worker.archive_existing_news_snapshot()
                self.assertEqual(upload.call_count, 1)

    def test_existing_r2_archive_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "news.json"
            file.write_bytes(b'{"ok":true}')
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            key = f"news/archive/20261113/{digest}.json"
            resp = mock.Mock(status_code=412)
            with mock.patch.dict("os.environ", {"R2_ACCESS_KEY_ID": "fake", "R2_SECRET_ACCESS_KEY": "fake"}), \
                 mock.patch.object(r2.requests, "put", return_value=resp) as req:
                self.assertTrue(r2.upload_file(file, object_key=key))
                self.assertEqual(req.call_args.kwargs["headers"]["If-None-Match"], "*")


if __name__ == "__main__":
    unittest.main()
