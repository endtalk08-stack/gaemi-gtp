"""News storage is additive, 7-day limited, and disconnected from existing UI."""
import datetime
import json
import os
import sys
import types
import unittest
from unittest.mock import patch

from backend.services import news_metadata_store as subject

_NOW = datetime.datetime(2026, 10, 15, 9, tzinfo=datetime.timezone.utc)

def _item(url, pubdate):
    return {
        "title": "미국 경제 기사", "description": "내용",
        "link": url, "pubDate": pubdate,
    }

class NewsMetadataStoreTests(unittest.TestCase):
    def test_retains_existing_and_appends_new(self):
        old = _item("https://news.example/old", "Wed, 14 Oct 2026 08:00:00 GMT")
        new = _item("https://news.example/new", "Thu, 15 Oct 2026 08:00:00 GMT")
        result = subject._retained_news([old], [new, old], now=_NOW)
        self.assertEqual({x["link"] for x in result}, {old["link"], new["link"]})

    def test_removes_only_seven_day_old_news(self):
        old = _item("https://news.example/expired", "Wed, 07 Oct 2026 08:00:00 GMT")
        recent = _item("https://news.example/recent", "Wed, 14 Oct 2026 08:00:00 GMT")
        kept = subject._retained_news([old, recent], [], now=_NOW)
        self.assertEqual([x["link"] for x in kept], [recent["link"]])

    def test_undated_news_keeps_original_first_seen(self):
        old = {"title": "미국 증시 소식", "link": "https://news.example/unknown",
               "_news_first_seen": "2026-10-14T09:00:00+00:00"}
        newer = {"title": "미국 증시 소식", "link": "https://news.example/unknown"}
        kept = subject._retained_news([old], [newer], now=_NOW)
        self.assertEqual(kept[0]["_news_first_seen"], old["_news_first_seen"])
        expired = subject._retained_news([old], [],
                  now=_NOW + datetime.timedelta(days=7))
        self.assertEqual(expired, [])

    def test_redis_merges_instead_of_replacing_and_uses_seven_day_ttl(self):
        values = {}
        class Redis:
            def __init__(self, **_): pass
            def get(self, key): return values.get(key)
            def set(self, key, value, ex=None):
                self.expiry = ex
                values[key] = value
                self.__class__.last_expiry = ex

        fake = types.SimpleNamespace(Redis=Redis)
        env = {"UPSTASH_REDIS_REST_URL": "https://example.test",
               "UPSTASH_REDIS_REST_TOKEN": "test", "NEWS_DATABASE_URL": ""}
        with patch.dict(os.environ, env), patch.dict(sys.modules, {"upstash_redis": fake}):
            subject._save([_item("https://news.example/one", "Wed, 14 Oct 2026 08:00:00 GMT")], "미국", 10, 1)
            subject._save([_item("https://news.example/two", "Wed, 15 Oct 2026 08:00:00 GMT")], "미국", 10, 1)
        merged = json.loads(values[subject._cache_key("미국", 10, 1)])
        self.assertEqual(len(merged), 2)
        self.assertEqual(Redis.last_expiry, 7 * 24 * 60 * 60)

    def test_read_cached_news_uses_redis_without_live_api(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        article = _item("https://news.example/cache-hit",
                        now.strftime("%a, %d %b %Y %H:%M:%S GMT"))
        class Redis:
            def __init__(self, **_): pass
            def get(self, key): return json.dumps([article])
        fake = types.SimpleNamespace(Redis=Redis)
        with patch.dict(sys.modules, {"upstash_redis": fake}), patch.dict(
            os.environ, {"UPSTASH_REDIS_REST_URL": "https://example.test",
                         "UPSTASH_REDIS_REST_TOKEN": "test",
                         "NEWS_DATABASE_URL": ""},
        ):
            rows = subject.read_cached_news("테스트", 20, 1)
        self.assertEqual([r["link"] for r in rows], [article["link"]])

    def test_read_cached_news_falls_back_to_neon(self):
        from backend.services import news_feed
        now = datetime.datetime.now(datetime.timezone.utc)
        calls = []
        class Cursor:
            def execute(self, statement, params):
                calls.append((statement, params))
            def fetchall(self):
                return [("테스트 기사", "요약", "https://news.example/db",
                         now, now)]
            def __enter__(self): return self
            def __exit__(self, *args): return False
        class Conn:
            def cursor(self): return Cursor()
            def __enter__(self): return self
            def __exit__(self, *args): return False
        fake = types.SimpleNamespace(connect=lambda *args, **kw: Conn())
        with patch.dict(sys.modules, {"psycopg": fake}), patch.dict(
            os.environ, {"NEWS_DATABASE_URL": "postgresql://placeholder/db",
                         "UPSTASH_REDIS_REST_URL": "",
                         "UPSTASH_REDIS_REST_TOKEN": ""},
        ):
            rows = subject.read_cached_news("테스트", 20, 1)
        self.assertEqual(rows[0]["title"], "테스트 기사")
        self.assertIn("retention_expires_at > now()", calls[0][0])
        self.assertEqual(calls[0][1][0], "테스트")

    def test_existing_news_feed_reads_storage_before_provider(self):
        from backend.services import news_feed
        now = datetime.datetime.now(datetime.timezone.utc)
        row = _item("https://news.example/fast",
                    now.strftime("%a, %d %b %Y %H:%M:%S GMT"))
        with patch.object(news_feed, "read_cached_news", return_value=[row]), \
             patch.object(news_feed, "_schedule_refresh") as refresh, \
             patch.object(news_feed.naver_news, "search_news") as provider:
            got = news_feed._fetch_query("cache-test-unique-4872", display=20)
        self.assertEqual(got[0]["link"], row["link"])
        provider.assert_not_called()
        refresh.assert_called_once()

    def test_latest_news_merges_into_existing_news_without_ui_changes(self):
        from backend.services import news_feed
        now = datetime.datetime.now(datetime.timezone.utc)
        old = _item("https://news.example/old",
                    (now - datetime.timedelta(days=1)).strftime("%a, %d %b %Y %H:%M:%S GMT"))
        new = _item("https://news.example/new",
                    now.strftime("%a, %d %b %Y %H:%M:%S GMT"))
        key = ("cache-refresh-test-unique-4872", 20, 1)
        with patch.object(news_feed.naver_news, "search_news", return_value=[new]), \
             patch.object(news_feed, "save_async") as save:
            news_feed._refresh_query(key, key[0], 20, 1, [old])
        self.assertEqual(
            {item["link"] for item in news_feed._CACHE[key][1]},
            {old["link"], new["link"]},
        )
        save.assert_called_once()

    def test_db_retention_uses_original_published_date_not_refresh_time(self):
        calls = []
        class Cursor:
            def execute(self, sql, params=None): calls.append((sql, params))
            def __enter__(self): return self
            def __exit__(self, *args): return False
        class Conn:
            def cursor(self): return Cursor()
            def __enter__(self): return self
            def __exit__(self, *args): return False

        fake = types.SimpleNamespace(connect=lambda *a, **kw: Conn())
        row = _item("https://news.example/one", "Wed, 14 Oct 2026 08:00:00 GMT")
        with patch.dict(sys.modules, {"psycopg": fake}), patch.dict(
            os.environ, {"NEWS_DATABASE_URL": "postgresql://placeholder/db",
                         "UPSTASH_REDIS_REST_URL": ""},
        ), patch.object(subject, "_expire"):
            subject._save([row], "미국", 10, 1)
        statements = [(sql, params) for sql, params in calls
                      if "INSERT INTO public.news_articles" in sql]
        self.assertEqual(len(statements), 1)
        self.assertIn("COALESCE(%s::timestamptz, now()) + interval '7 days'", statements[0][0])
        self.assertEqual(statements[0][1][-1], subject._timestamp(row["pubDate"]))
        self.assertIn("ON CONFLICT (url_hash)", statements[0][0])
        self.assertNotIn("licensed_body", statements[0][0])

if __name__ == "__main__":
    unittest.main()
