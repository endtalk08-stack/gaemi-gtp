"""Kiwoom ticker/name registration: no API, no DB access in these tests."""
import unittest
from unittest.mock import patch, MagicMock

from backend.kiwoom_us_identity_sync import identity_from_kiwoom, upsert_kiwoom_identity, repair_saved_top20
from backend.analysis.news.stock_identity import resolve_us_identity


# Actual Kiwoom Top 20 rows captured in Neon on 2026-10-24 KST.
TOP20 = [
    ("MU", "마이크론 테크놀로지"), ("NVDA", "엔비디아"),
    ("SPCX", "스페이스X"), ("TSLA", "테슬라"),
    ("AAPL", "애플"), ("META", "메타 플랫폼스(페이스북)"),
    ("SNDK", "샌디스크"), ("AMD", "AMD"),
    ("MSFT", "마이크로소프트"), ("AMZN", "아마존닷컴"),
    ("INTC", "인텔"), ("GOOGL", "알파벳 A"),
    ("BE", "블룸 에너지"), ("AVGO", "브로드컴"),
    ("WDC", "웨스턴 디지털"), ("MRNA", "모더나"),
    ("PLTR", "팔란티어 테크"),
    ("STX", "시게이트 테크놀로지 홀딩스"),
    ("GOOG", "알파벳 C"),
    ("CRWD", "크라우드스트라이크 홀딩스"),
]


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, args):
        self.calls.append((sql, args))


class IdentitySyncTests(unittest.TestCase):
    def test_twenty_ranking_pairs_are_unique_source_confirmed_matches(self):
        self.assertEqual(len({ticker for ticker, _ in TOP20}), 20)
        for ticker, name in TOP20:
            with self.subTest(ticker=ticker):
                row = identity_from_kiwoom(name, ticker)
                self.assertEqual(row["ticker"], ticker)
                self.assertEqual(row["status"], "verified")
                self.assertTrue(row["company_key"])
                self.assertTrue(row["news_name"])

    def test_share_classes_have_distinct_tickers_and_common_company_key(self):
        a = identity_from_kiwoom("알파벳 A", "GOOGL")
        c = identity_from_kiwoom("알파벳 C", "GOOG")
        self.assertEqual(a["company_key"], c["company_key"])
        self.assertNotEqual(a["ticker"], c["ticker"])
        self.assertEqual(a["news_name"], "알파벳")

    def test_existing_alias_and_independent_new_company(self):
        self.assertEqual(identity_from_kiwoom("메타 플랫폼스(페이스북)", "META")["news_name"], "메타")
        self.assertEqual(identity_from_kiwoom("팔란티어 테크", "PLTR")["company_key"], "US:PLTR")
        new = identity_from_kiwoom("신규 미등록 기업", "NEW")
        self.assertEqual((new["status"], new["company_key"], new["news_name"]),
                         ("verified", "US:NEW", "신규 미등록 기업"))

    def test_known_ticker_with_wrong_company_does_not_become_verified(self):
        self.assertEqual(identity_from_kiwoom("엔비디아", "AAPL")["status"], "pending")
        self.assertEqual(identity_from_kiwoom("알파벳 C", "GOOGL")["status"], "pending")
        self.assertEqual(resolve_us_identity("엔비디아", "AAPL")["status"], "pending")
        self.assertIsNone(identity_from_kiwoom("무효", "NEW!"))

    def test_existing_saved_identities_do_not_repeat_offsession_writes(self):
        import sys
        db = MagicMock()
        conn = db.connect.return_value.__enter__.return_value
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = [
            (rank, ticker, name, None,
             result["company_key"], result["news_name"], result["status"], True)
            for rank, (ticker, name) in enumerate(TOP20, start=1)
            for result in [identity_from_kiwoom(name, ticker)]
        ]
        with patch.dict(sys.modules, {"psycopg": db}):
            report = repair_saved_top20("test-dsn")
        self.assertEqual(report, {"rows": 20, "verified": 20, "updated": 0})
        self.assertEqual(cur.execute.call_count, 1)

    def test_upsert_does_not_write_news_ai_or_rankings(self):
        cursor = FakeCursor()
        identity = upsert_kiwoom_identity(cursor, "WDC", "웨스턴 디지털", "NASDAQ")
        self.assertEqual(identity["company_key"], "US:WDC")
        self.assertEqual(len(cursor.calls), 1)
        sql, params = cursor.calls[0]
        self.assertIn("public.market_instruments", sql)
        self.assertNotIn("public.news_processed_snapshots", sql)
        self.assertNotIn("public.market_rank_entries", sql)
        self.assertNotIn("public.market_rank_snapshots", sql)
        self.assertEqual(params, ("WDC", "웨스턴 디지털", "NASDAQ", "US:WDC",
                                  "웨스턴 디지털", "verified"))
        self.assertIn("THEN 'review'", sql)


if __name__ == "__main__":
    unittest.main()
