"""Offline persistence checks: no Neon writes or AI calls."""
from datetime import date
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops"))
from staged_ai_issue_store import save_ai_issues, read_issue_sources, SOURCES_RESULT_TYPE


class Cursor:
    def __init__(self):
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, query, params):
        self.calls.append((query, params))
    def fetchone(self):
        return (100 + len(self.calls),)


class Conn:
    def __init__(self):
        self.cur = Cursor()
        self.transactions = 0
    def cursor(self):
        return self.cur
    def transaction(self):
        self.transactions += 1
        return self
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class StoreTests(unittest.TestCase):
    def test_zero_issues_no_connection_needed(self):
        self.assertEqual(save_ai_issues(None, [], market="US", symbol="NVDA",
                                        exchange_day=date(2026, 10, 17)), [])

    def test_two_issues_existing_connection(self):
        conn = Conn()
        issues = [
            {"headline": "수요", "summary": "수요 확대", "tags": ["#수요"]},
            {"headline": "투자", "summary": "투자 확대", "tags": ["#투자"]},
        ]
        result = save_ai_issues(conn, issues, market="KR", symbol="005930",
                                exchange_day=date(2026, 10, 17))
        self.assertEqual(result, [101, 102])
        self.assertEqual(conn.transactions, 1)
        self.assertEqual(len(conn.cur.calls), 2)
        self.assertIn("news_ai_issues", conn.cur.calls[0][0])
        self.assertIn('"#수요"', conn.cur.calls[0][1][5])

    def test_atomic_ai_and_article_bundle_in_existing_24h_table(self):
        conn = Conn()
        ai = [{"headline": "AI 부채", "summary": "회사채 금리 상승",
               "tags": ["#금리"], "source_ids": [1]}]
        sources = [[{
            "source_id": 1, "title": "회사채 뉴스", "description": "설명만 저장",
            "published_at": "2026-10-17T18:16:00+00:00",
            "source": "신문", "url": "https://example.org/article",
            "body": "본문은 절대 저장되면 안 됨",
        }]]
        ids = save_ai_issues(conn, ai, market="US", symbol="브로드컴",
                             exchange_day=date(2026, 10, 17),
                             sources_by_issue=sources)
        self.assertEqual(ids, [101])
        self.assertEqual(conn.transactions, 1)
        statements = [sql for sql, _ in conn.cur.calls]
        self.assertTrue(any("INSERT INTO public.news_ai_issues" in x for x in statements))
        bundles = [(sql, params) for sql, params in conn.cur.calls
                   if "INSERT INTO public.news_processed_results_24h" in sql]
        self.assertEqual(len(bundles), 1)
        sql, params = bundles[0]
        self.assertIn("24 hours", sql)
        self.assertEqual(params[0], SOURCES_RESULT_TYPE)
        payload = __import__("json").loads(params[2])
        self.assertEqual(payload["issues"][0]["issue_id"], 101)
        self.assertEqual(payload["issues"][0]["source_articles"][0]["source"], "신문")
        self.assertEqual(payload["issues"][0]["source_articles"][0]["description"], "설명만 저장")
        self.assertNotIn("body", payload["issues"][0]["source_articles"][0])
        self.assertEqual(payload["issues"][0]["source_articles"][0]["url"], "https://example.org/article")
        self.assertTrue(any("expires_at<=now()" in x and SOURCES_RESULT_TYPE in str(p)
                            for x,p in conn.cur.calls))

    def test_no_article_provenance_refuses_ai_issue_save(self):
        conn = Conn()
        ai = [{"headline": "뉴스", "summary": "내용", "tags": []}]
        with self.assertRaises(ValueError):
            save_ai_issues(conn, ai, market="US", symbol="브로드컴",
                           exchange_day=date(2026, 10, 17),
                           sources_by_issue=[[]])
        self.assertEqual(conn.cur.calls, [])

    def test_retrieve_bundle_without_expired_sources(self):
        class ResultCursor:
            def __init__(self):
                self.query = None
                self.params = None
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def execute(self, sql, params):
                self.query, self.params = sql, params
            def fetchone(self):
                return ({"issues":[{"issue_id":7,"source_articles":[
                    {"title":"테스트","published_at":"2026-10-17T18:16:00+00:00"}]}]},)
        class ResultConn:
            def __init__(self): self.cur=ResultCursor()
            def cursor(self): return self.cur
        conn=ResultConn()
        sources=read_issue_sources(conn,market="US",symbol="메타",
                                   exchange_day=date(2026,10,17),issue_ids=[7,9])
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0][0]["title"], "테스트")
        self.assertEqual(sources[1], [])
        self.assertIn("expires_at>now()", conn.cur.query)

    def test_reject_missing_connection(self):
        with self.assertRaises(ValueError):
            save_ai_issues(None, [{"headline": "제목", "summary": "내용", "tags": []}],
                           market="US", symbol="NVDA", exchange_day=date(2026, 10, 17))


if __name__ == "__main__":
    unittest.main()
