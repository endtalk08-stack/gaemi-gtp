"""Only the news worker gets a bounded article timeout change."""
import io
import os
import unittest
import urllib.error
from unittest.mock import patch

from backend.services import news_detail


class WorkerDetailTimeoutTests(unittest.TestCase):
    def test_news_worker_timeout_is_bounded(self):
        with patch.dict(os.environ, {"GAEMIGTP_NEWS_WORKER": "1"}):
            self.assertEqual(news_detail._article_request_timeout(), 3.0)

    def test_render_timeout_is_unchanged(self):
        with patch.dict(os.environ, {"GAEMIGTP_NEWS_WORKER": ""}):
            self.assertEqual(news_detail._article_request_timeout(), 1.6)

    def test_timeout_passed_to_single_urlopen_call(self):
        url = "https://example.org/verified-timeout-test"
        with patch.dict(os.environ, {"GAEMIGTP_NEWS_WORKER": "1"}), \
             patch.object(news_detail.urllib.request, "urlopen",
                          side_effect=TimeoutError("timed out")) as request, \
             patch("sys.stdout", new_callable=io.StringIO):
            out = news_detail._read_url(url, with_source=True)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs["timeout"], 3.0)
        self.assertEqual(out, {"text": "", "source": "fetch_failed"})

    def test_http_403_is_not_retried_and_is_not_rebranded_as_success(self):
        url = "https://example.org/verified-403-test"
        forbidden = urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        with patch.dict(os.environ, {"GAEMIGTP_NEWS_WORKER": "1"}), \
             patch.object(news_detail.urllib.request, "urlopen",
                          side_effect=forbidden) as request, \
             patch("sys.stdout", new_callable=io.StringIO):
            out = news_detail._read_url(url, with_source=True)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(out, {"text": "", "source": "fetch_failed"})


if __name__ == "__main__":
    unittest.main()
