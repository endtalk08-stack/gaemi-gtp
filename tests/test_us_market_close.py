"""Offline checks: only NAVER API headline/description, never publisher pages."""
import datetime as dt
import json
import unittest
from unittest.mock import patch

from backend.services import us_market_close as close


def row(i, *, domain="yna.co.kr", day=19, hour=17, desc=None, title=None):
    return {
        "raw_title": title or f"뉴욕증시 마감…시장 움직임과 주요 뉴스 {i}",
        "raw_description": desc or f"미국 증시 마감 후 확인된 시장 동향과 기업 움직임을 요약한 내용 {i}",
        "raw_original_link": f"https://{domain}/news/{i}",
        "raw_pub_date": dt.datetime(
            2026, 10, day, hour, tzinfo=close.NY,
        ).strftime("%a, %d %b %Y %H:%M:%S %z"),
    }


class UsMarketCloseTests(unittest.TestCase):
    def setUp(self):
        self.session = dt.date(2026, 10, 19)
        self.now = dt.datetime(2026, 10, 19, 22, tzinfo=close.UTC)

    def test_rejects_older_session_intraday_and_missing_description(self):
        rows = [
            row(1),
            row(2, day=18),
            row(3, hour=15),
            row(4, desc="짧음"),
            row(5, title="코스피 증시 마감…국내 증시"),
            row(6, domain="news.example.com"),
        ]
        result = close.select_close_articles(rows, self.session, self.now)
        self.assertEqual([a["url"] for a in result], [
            "https://yna.co.kr/news/1",
            "https://news.example.com/news/6",
        ])

    def test_native_naver_raw_description_instead_of_article_body(self):
        news = [
            {**row(1), "raw_title": "<b>뉴욕증시</b> 마감, 상승 전환",
             "raw_description": "주요 기술주가 거래 후반 상승하면서 미국 증시는 상승 마감했다."},
            row(2, domain="hankyung.com"),
        ]
        result = close.collect_articles(
            self.session, now_utc=self.now,
            search=lambda *args, **kwargs: news,
            reader=lambda *_a, **_k: self.fail("article page fetch is forbidden"),
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "뉴욕증시 마감, 상승 전환")
        self.assertIn("description", result[0])
        self.assertNotIn("body", result[0])

    def test_top_ten_deduped_two_per_publisher(self):
        news = [row(i,domain=f"publisher{i//2}.example.com") for i in range(15)]
        news.append(row(2,domain="another.example.com"))
        result = close.select_close_articles(news, self.session, self.now)
        self.assertEqual(len(result), 10)
        self.assertEqual(len(set(x["title"] for x in result)), 10)
        self.assertTrue(all("description" in x for x in result))

    def test_prompt_explicitly_disallows_invented_market_data(self):
        prompt = close._prompt(close.select_close_articles([
            row(1),row(2,domain="mk.co.kr")
        ],self.session,self.now),self.session)
        self.assertIn("미국장은 어땠어?",prompt)
        self.assertIn("제목과 짧은 소개",prompt)
        self.assertIn("추정 숫자를 절대 쓰지 마",prompt)
        self.assertNotIn('"article_text"',prompt)
        self.assertNotIn('"body"',prompt)

    def test_120b_is_fixed_and_only_one_provider_call(self):
        self.assertEqual(close.MODEL, "openai/gpt-oss-120b")
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self):
                return json.dumps({"choices":[{"message":{"content":"증시 분석 내용 " * 25}}]}).encode()
        with patch.dict(close.os.environ, {"GROQ_API_KEY":"offline-test","US_CLOSE_GROQ_MODEL":"wrong"}), \
            patch.object(close.urllib.request,"urlopen",return_value=FakeResponse()) as api:
            answer=close._generate([row(1) | {"title":"뉴욕증시 마감","description":"뉴스 설명"}],self.session)
        self.assertIn("증시 분석",answer)
        self.assertEqual(api.call_count,1)
        req=api.call_args.args[0]
        self.assertEqual(json.loads(req.data)["model"],"openai/gpt-oss-120b")

    def test_insufficient_snippets_never_calls_database_or_ai(self):
        with patch.object(close,"collect_articles",return_value=[row(1)]), \
            patch.object(close,"_connection",side_effect=AssertionError("DB called")):
            result=close.publish_once(now_utc=self.now)
        self.assertEqual(result["status"],"insufficient_news_snippets")

    def test_duplicate_session_never_spends_on_ai(self):
        class Duplicate:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def cursor(self):return self
            def execute(self,*args):pass
            def fetchone(self):return None
        with patch.object(close,"collect_articles",return_value=[row(1),row(2)]), \
            patch.object(close,"_connection",return_value=Duplicate()):
            result=close.publish_once(now_utc=self.now,generator=lambda *_: self.fail("duplicate AI"))
        self.assertEqual(result["status"],"already_attempted")

    def test_publishes_only_ai_text_and_metadata_not_snippet(self):
        calls=[]
        class Connection:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def cursor(self):return self
            def execute(self,sql,params=None):calls.append((sql,params))
            def fetchone(self):return (self_date,)
        self_date=self.session
        articles=[row(1) | {"title":"뉴욕증시 마감 A","description":"PRIVATE_SNIPPET_NEVER_IN_DATABASE"},
                  row(2) | {"title":"뉴욕증시 마감 B","description":"PRIVATE_SNIPPET_NEVER_IN_DATABASE_B"}]
        articles=[{"title":a["title"],"description":a["description"],"url":a["raw_original_link"],
                   "published_at":"2026-10-19T17:00:00-04:00","publisher":"yna.co.kr"} for a in articles]
        with patch.object(close,"collect_articles",return_value=articles), \
            patch.object(close,"_connection",return_value=Connection()):
            result=close.publish_once(now_utc=self.now,generator=lambda *_:"AI 검증된 마감 분석 "*20)
        self.assertEqual(result["status"],"published")
        written=str(calls)
        self.assertNotIn("PRIVATE_SNIPPET_NEVER_IN_DATABASE",written)
        self.assertIn("AI 검증된 마감 분석",written)

    def test_weekend_does_not_consume_provider(self):
        weekend=dt.datetime(2026,10,17,22,tzinfo=close.UTC)
        result=close.publish_once(now_utc=weekend,search=lambda *_a,**_k:self.fail("weekend"))
        self.assertEqual(result["status"],"market_not_closed")


if __name__=="__main__":
    unittest.main()
