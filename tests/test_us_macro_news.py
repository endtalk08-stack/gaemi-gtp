import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

import backend.us_macro_news as job

NOW = dt.datetime(2026, 11, 27, 18, 0, tzinfo=dt.timezone.utc)


def rss(*items):
    body = "".join("<item><title>%s</title><link>%s</link><pubDate>%s</pubDate></item>" % i for i in items)
    return ("<rss><channel>%s</channel></rss>" % body).encode()


RECENT = "Thu, 26 Nov 2026 14:00:00 GMT"
OLD = "Sun, 15 Nov 2026 14:00:00 GMT"


class RulesTest(unittest.TestCase):
    def test_white_house_keeps_market_topics_only(self):
        rows = job.parse_feed(rss(
            ("Thanksgiving Day, 2026", "https://www.whitehouse.gov/a", RECENT),
            ("First Lady Melania Trump Hails Armed Forces", "https://www.whitehouse.gov/b", RECENT),
            ("President Trump Raises Tariffs on Chinese Semiconductors", "https://www.whitehouse.gov/c", RECENT),
            ("Gas Prices Plunge Ahead of the Holiday Season", "https://www.whitehouse.gov/d", RECENT),
        ), "백악관", "정책·규제", "market", NOW)
        self.assertEqual([r["title_en"] for r in rows], ["President Trump Raises Tariffs on Chinese Semiconductors"])

    def test_fed_feed_keeps_everything_recent_and_https_only(self):
        rows = job.parse_feed(rss(
            ("Federal Reserve issues FOMC statement", "https://www.federalreserve.gov/x", RECENT),
            ("Old statement", "https://www.federalreserve.gov/y", OLD),
            ("Insecure link", "http://example.com/z", RECENT),
        ), "연준", "연준·금리", "all", NOW)
        self.assertEqual([r["title_en"] for r in rows], ["Federal Reserve issues FOMC statement"])
        self.assertEqual(rows[0]["category"], "연준·금리")
        self.assertRegex(rows[0]["id"], r"^[a-f0-9]{16}$")


class RunTest(unittest.TestCase):
    def setUp(self):
        self.state = Path(tempfile.mkdtemp()) / "state.json"
        self.uploads = []
        self.rows = [{"id": "a" * 16, "source": "연준", "category": "연준·금리",
                      "title_en": "Federal Reserve issues FOMC statement",
                      "url": "https://www.federalreserve.gov/x", "published_at": NOW.isoformat()}]
        self.translated = []

    def translator(self, texts):
        self.translated.append(list(texts))
        return ["연준, FOMC 성명 발표"] * len(texts), "deepl"

    def run_job(self, translator=None):
        return job.run(NOW, collector=lambda now: [dict(r) for r in self.rows],
                       translator=translator or self.translator,
                       upload=lambda payload, key: self.uploads.append((key, payload)), state_path=self.state)

    def test_translates_only_new_headlines_once(self):
        self.assertEqual(self.run_job()["new"], 1)
        self.assertEqual(self.uploads[0][0], "news/macro/us/feed.json")
        self.assertEqual(self.uploads[0][1]["items"][0]["title"], "연준, FOMC 성명 발표")
        self.assertEqual(self.run_job()["status"], "unchanged")      # already known: no DeepL call
        self.assertEqual(len(self.translated), 1)
        self.assertEqual(len(self.uploads), 1)

    def test_nothing_is_published_without_a_translation(self):
        def broken(texts):
            raise RuntimeError("deepl_key_missing")
        self.assertEqual(self.run_job(broken)["status"], "translate_failed")
        self.assertEqual(self.uploads, [])
        self.assertEqual(self.run_job()["new"], 1)                    # retried once the key works

    def test_translate_requires_a_key(self):
        with self.assertRaises(RuntimeError):
            job.translate_deepl(["x"], api_key=" ")
        with self.assertRaises(RuntimeError):
            job.translate_google(["x"], api_key=" ")

    def test_google_takes_over_when_deepl_fails(self):
        def deepl(texts):
            raise RuntimeError("deepl_http_456")              # monthly limit used up
        out = job.translate(["hello"], providers=(("deepl", deepl), ("google", lambda t: ["안녕"])))
        self.assertEqual(out, (["안녕"], "google"))
        with self.assertRaises(RuntimeError) as ctx:
            job.translate(["hello"], providers=(("deepl", deepl), ("google", deepl)))
        self.assertIn("deepl_http_456", str(ctx.exception))

    def test_translate_uses_free_endpoint_for_free_keys(self):
        seen = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"translations": [{"text": "안녕"}]}).encode()

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["auth"] = request.headers["Authorization"]
            return Response()
        self.assertEqual(job.translate_deepl(["hello"], api_key="k:fx", opener=opener), ["안녕"])
        self.assertEqual(seen["url"], "https://api-free.deepl.com/v2/translate")
        self.assertEqual(seen["auth"], "DeepL-Auth-Key k:fx")


if __name__ == "__main__":
    unittest.main()
