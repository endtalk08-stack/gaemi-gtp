import datetime
import unittest

from backend.analysis.news.scoring import build_connected_keyword_test
from backend.providers.official_company_news import _parse_feed_bytes
from backend.providers.sec_filings import _normalize_recent_filings


class OfficialCompanyNewsProviderTests(unittest.TestCase):
    def test_parses_rss_as_trusted_company_source(self):
        payload = b"""<?xml version="1.0"?>
        <rss><channel><item>
          <title>Google launches new enterprise AI agent</title>
          <description>Google introduced a new Gemini tool for business users.</description>
          <pubDate>Thu, 08 Oct 2026 16:00:00 GMT</pubDate>
          <link>https://blog.google/example</link>
        </item></channel></rss>"""

        rows = _parse_feed_bytes(
            payload,
            stock_name="알파벳",
            source_name="Google Blog",
            feed_url="https://blog.google/rss/",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider_stock"], "알파벳")
        self.assertEqual(rows[0]["source_type"], "official_company")
        self.assertEqual(rows[0]["source_quality"], 100)

    def test_trusted_official_feed_marks_event_owner_direct_without_name_in_title(self):
        result = build_connected_keyword_test([{
            "title": "Launches new enterprise AI agent",
            "description": "A new product was unveiled for business users.",
            "provider_stock": "알파벳",
            "source_type": "official_company",
            "source": "Google Blog",
        }], "알파벳", max_keywords=3)

        article = result["articles"][0]
        self.assertEqual(article["relation_type"], "direct")
        self.assertEqual(article["event_owner"], "알파벳")


class SecProviderTests(unittest.TestCase):
    def test_normalizes_recent_8k_without_network(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "filings": {
                "recent": {
                    "form": ["8-K"],
                    "filingDate": [now.date().isoformat()],
                    "acceptanceDateTime": [now.isoformat()],
                    "accessionNumber": ["0001652044-26-000001"],
                    "primaryDocument": ["goog-20261008.htm"],
                    "primaryDocDescription": ["Current report"],
                    "items": ["2.02,9.01"],
                }
            }
        }

        rows = _normalize_recent_filings(
            payload,
            stock_name="알파벳",
            ticker="GOOGL",
            cik=1652044,
            days=7,
            limit=5,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_type"], "sec_filing")
        self.assertEqual(rows[0]["provider_stock"], "알파벳")
        self.assertEqual(rows[0]["sec_form"], "8-K")
        self.assertIn("sec.gov/Archives/edgar/data/1652044/", rows[0]["url"])


    def test_prefers_summary_over_full_content_and_caps_analysis_text(self):
        long_content = "full article body " * 500
        payload = f"""<?xml version="1.0"?>
        <feed>
          <entry>
            <title>Introducing the Gemini agent</title>
            <content>{long_content}</content>
            <summary>Short official summary for Gemini.</summary>
            <published>2026-10-08T16:00:00Z</published>
            <link href="https://blog.google/example" rel="alternate" />
          </entry>
        </feed>""".encode("utf-8")

        rows = _parse_feed_bytes(
            payload,
            stock_name="알파벳",
            source_name="Google Blog",
            feed_url="https://blog.google/rss/",
        )

        self.assertEqual(rows[0]["description"], "Short official summary for Gemini.")

    def test_caps_long_official_description_before_scoring(self):
        long_description = "Google announced a Gemini product update. " * 100
        payload = f"""<?xml version="1.0"?>
        <rss><channel><item>
          <title>Google launches new Gemini product</title>
          <description>{long_description}</description>
          <pubDate>Thu, 08 Oct 2026 16:00:00 GMT</pubDate>
          <link>https://blog.google/example</link>
        </item></channel></rss>""".encode("utf-8")

        rows = _parse_feed_bytes(
            payload,
            stock_name="알파벳",
            source_name="Google Blog",
            feed_url="https://blog.google/rss/",
        )

        self.assertLessEqual(len(rows[0]["description"]), 1200)
        self.assertTrue(rows[0]["description"].startswith("Google announced"))


if __name__ == "__main__":
    unittest.main()
