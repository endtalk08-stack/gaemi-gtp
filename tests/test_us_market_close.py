import datetime as dt
import json
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

    def test_real_naver_provider_raw_fields_are_selected(self):
        # backend.providers.naver_news.fetch_news returns raw_* keys, not
        # title/originallink/pubDate. This must work without changing it.
        rows = [
            {
                "raw_title": "<b>뉴욕증시</b> 마감…기술주 상승",
                "raw_original_link": "https://www.yna.co.kr/economy/closing",
                "raw_link": "https://n.news.naver.com/article/001/1",
                "raw_pub_date": dt.datetime(2026, 10, 16, 17,
                                            tzinfo=close.NY).strftime("%a, %d %b %Y %H:%M:%S %z"),
            },
            {
                "raw_title": "뉴욕증시 마감…경제지표",
                "raw_original_link": "https://www.hankyung.com/economy/closing",
                "raw_pub_date": dt.datetime(2026, 10, 16, 17,
                                            tzinfo=close.NY).strftime("%a, %d %b %Y %H:%M:%S %z"),
            },
        ]
        chosen = close.select_close_articles(rows, self.session, self.now)
        self.assertEqual(len(chosen), 2)
        self.assertEqual(chosen[0]["title"], "뉴욕증시 마감…기술주 상승")
        self.assertEqual(chosen[0]["publisher"], "yna.co.kr")
        self.assertTrue(chosen[0]["url"].startswith("https://www.yna.co.kr/"))

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

    def test_market_close_uses_120b_only_even_with_legacy_env_override(self):
        self.assertEqual(close.MODEL, "openai/gpt-oss-120b")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": "검증된 마감시황 " * 15}}]}).encode()

        article = [{"title": "뉴욕증시 마감", "published_at": "2026-10-16T17:00-04:00",
                    "body": "검증된 마감 기사 본문"}]
        with patch.dict(close.os.environ, {
            "GROQ_API_KEY": "offline-test-placeholder",
            "US_CLOSE_GROQ_MODEL": "openai/gpt-oss-20b",
        }), patch.object(close.urllib.request, "urlopen", return_value=FakeResponse()) as mocked:
            answer = close._generate(article, self.session)
        self.assertIn("검증된 마감시황", answer)
        request = mocked.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "openai/gpt-oss-120b")

    def test_insufficient_articles_never_calls_database_or_ai(self):
        with patch.object(close, "collect_articles", return_value=[{"body": "abc"}]), \
             patch.object(close, "_connection", side_effect=AssertionError("DB called")):
            result = close.publish_once(now_utc=self.now)
        self.assertEqual(result["status"], "insufficient_full_articles")

    def test_duplicate_session_never_calls_120b_again(self):
        class DuplicateConnection:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def cursor(self): return self
            def execute(self, *args): return None
            def fetchone(self): return None

        articles = [
            {"title": "뉴욕증시 마감", "published_at": "2026-10-16T17:00-04:00",
             "url": "https://yna.co.kr/market/a", "publisher": "yna.co.kr",
             "body": "검증된 본문" * 100},
            {"title": "뉴욕증시 마감", "published_at": "2026-10-16T17:20-04:00",
             "url": "https://hankyung.com/market/b", "publisher": "hankyung.com",
             "body": "추가 본문" * 100},
        ]
        with patch.object(close, "collect_articles", return_value=articles), \
             patch.object(close, "_connection", return_value=DuplicateConnection()):
            outcome = close.publish_once(
                now_utc=self.now,
                generator=lambda *_: self.fail("Unexpected repeated AI call")
            )
        self.assertEqual(outcome["status"], "already_attempted")

    def test_publishes_only_edited_content_not_source_body(self):
        executed = []
        class MemoryConnection:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def cursor(self): return self
            def execute(self, sql, args=None): executed.append((sql, args))
            def fetchone(self): return (self_date,)

        self_date = self.session
        articles = [
            {"title": "뉴욕증시 마감", "published_at": "2026-10-16T17:00-04:00",
             "url": "https://yna.co.kr/market/a", "publisher": "yna.co.kr",
             "body": "DO_NOT_STORE_SOURCE_BODY_A" * 30},
            {"title": "뉴욕증시 마감", "published_at": "2026-10-16T17:20-04:00",
             "url": "https://hankyung.com/market/b", "publisher": "hankyung.com",
             "body": "DO_NOT_STORE_SOURCE_BODY_B" * 30},
        ]
        with patch.object(close, "collect_articles", return_value=articles), \
             patch.object(close, "_connection", return_value=MemoryConnection()):
            result = close.publish_once(now_utc=self.now,
                                        generator=lambda *_: "가공된 마감 분석 문장" * 10)
        self.assertEqual(result["status"], "published")
        written = " ".join(str(params) for _sql, params in executed)
        self.assertNotIn("DO_NOT_STORE_SOURCE_BODY_A", written)
        self.assertNotIn("DO_NOT_STORE_SOURCE_BODY_B", written)
        self.assertIn("가공된 마감 분석 문장", written)
        self.assertIn(close.MODEL, written)

    def test_weekend_does_not_search_or_call_ai(self):
        weekend = dt.datetime(2026, 10, 17, 22, tzinfo=close.UTC)
        result = close.publish_once(now_utc=weekend, search=lambda *a, **kw: self.fail("searched"))
        self.assertEqual(result["status"], "market_not_closed")


if __name__ == "__main__":
    unittest.main()
