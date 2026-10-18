import datetime as dt
import unittest
from unittest.mock import patch

from backend.services import us_market_close as close


def row(title, domain, hour=17, day=16):
    return {
        "title": title,
        "originallink": "https://" + domain + "/economy/story",
        "pubDate": dt.datetime(2026, 10, day, hour, tzinfo=close.NY).strftime(
            "%a, %d %b %Y %H:%M:%S %z"
        ),
    }


class UsMarketCloseTests(unittest.TestCase):
    def setUp(self):
        self.session = dt.date(2026, 10, 16)
        self.now = dt.datetime(2026, 10, 16, 22, tzinfo=close.UTC)

    def test_date_and_publishers_prevent_wrong_session(self):
        articles = [
            row("뉴욕증시 마감…기술주 혼조", "yna.co.kr", 17, 16),
            row("뉴욕증시 마감…전날 소식", "hankyung.com", 17, 15),
            row("뉴욕증시 마감…다른 해외사이트", "unknown.example", 17, 16),
            row("뉴욕증시 마감…장중", "mk.co.kr", 12, 16),
            row("뉴욕증시 상승…장중 흐름", "mk.co.kr", 17, 16),
        ]
        result = close.select_close_articles(articles, self.session, self.now)
        self.assertEqual([item["publisher"] for item in result], ["yna.co.kr"])

    def test_one_publisher_and_one_headline_only(self):
        news = [
            row("뉴욕증시 마감…주요 흐름", "yna.co.kr"),
            row("뉴욕증시 마감…또 다른 기사", "www.yna.co.kr"),
            row("뉴욕증시 마감…경제지표", "hankyung.com"),
        ]
        result = close.select_close_articles(news, self.session, self.now)
        self.assertEqual(len(result), 2)
        self.assertEqual(set(a["publisher"] for a in result), {"yna.co.kr", "hankyung.com"})

    def test_article_body_must_be_real_text_not_snippet(self):
        news = [row("뉴욕증시 마감…기술주", "yna.co.kr"),
                row("뉴욕증시 마감…채권시장", "hankyung.com"),
                row("뉴욕증시 마감…나스닥", "mk.co.kr")]
        def reader(items, limit=3, with_sources=False):
            return [
                {"source": "meta_description", "text": "설명 " * 300},
                {"source": "article_or_main_paragraphs", "text": "검증된 본문 " * 100},
                {"source": "jsonld_article_body", "text": "마감시황 본문 " * 100},
            ]
        result = close.collect_articles(self.session, now_utc=self.now,
                                        search=lambda *a, **kw: news, reader=reader)
        self.assertEqual(len(result), 2)
        self.assertTrue(all("body" in item for item in result))

    def test_prompt_has_no_six_category_quota(self):
        articles = [{"title": "뉴욕증시 마감", "published_at": "2026-10-16T17:00-04:00",
                     "body": "본문 내용"}] * 2
        prompt = close._prompt(articles, self.session)
        self.assertIn("미국장은 어땠어?", prompt)
        self.assertIn("분야를 억지로 채우지 마", prompt)
        self.assertNotIn("source_ids", prompt)

    def test_insufficient_articles_never_calls_database_or_ai(self):
        with patch.object(close, "collect_articles", return_value=[{"body": "abc"}]), \
             patch.object(close, "_connection", side_effect=AssertionError("DB called")):
            result = close.publish_once(now_utc=self.now)
        self.assertEqual(result["status"], "insufficient_full_articles")

    def test_weekend_does_not_search_or_call_ai(self):
        weekend = dt.datetime(2026, 10, 17, 22, tzinfo=close.UTC)
        result = close.publish_once(now_utc=weekend, search=lambda *a, **kw: self.fail("searched"))
        self.assertEqual(result["status"], "market_not_closed")


if __name__ == "__main__":
    unittest.main()
