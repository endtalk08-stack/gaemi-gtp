"""Offline tests: no external price, news, AI, disclosure or DB calls."""
import pathlib
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from backend.services.stock_scope import STOCKS, resolve_stock, public_stock_rows
from backend.services.stock_ai_issue_view import read_ai_issue_map, build_watchlist_result


class FakeCursor:
    def __init__(self, rows): self.rows = rows; self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params):
        self.calls.append((sql, params))
        assert "news_ai_issues" in sql
        assert "market_rank_" not in sql
        assert "news_processed_snapshots" not in sql
    def fetchall(self): return self.rows


class FakeConn:
    def __init__(self, rows): self.cursor_obj = FakeCursor(rows)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.cursor_obj


class Fixed40Tests(unittest.TestCase):
    def test_exact_two_groups_and_distinct_company(self):
        self.assertEqual(len(STOCKS), 40)
        self.assertEqual([sum(r["market"] == m for r in STOCKS) for m in ("KR", "US")], [20, 20])
        self.assertEqual(len({r["company_key"] for r in STOCKS}), 40)
        self.assertEqual(len(public_stock_rows()), 40)

    def test_synonyms_preserve_market_and_ticker(self):
        self.assertEqual(resolve_stock("GOOG")["symbol"], "GOOGL")
        self.assertEqual(resolve_stock("알파벳 Class A")["symbol"], "GOOGL")
        self.assertEqual(resolve_stock("TSMC ADR")["symbol"], "TSM")
        self.assertEqual(resolve_stock("SK하이닉스")["market"], "KR")
        self.assertEqual(resolve_stock("SK하이닉스 ADR")["market"], "US")
        self.assertEqual(resolve_stock("005930")["name"], "삼성전자")

    def test_reject_other_stocks_and_mismatched_codes(self):
        for s in ("팔란티어", "오라클", "모더나", "코어위브", "네이버", "PLTR", "QQQ"):
            self.assertIsNone(resolve_stock(s), s)
        self.assertIsNone(resolve_stock("삼성전자", market="US"))
        self.assertIsNone(resolve_stock("애플", market="US", symbol="NVDA"))

    def test_saved_ai_issues_join_names_and_bodies(self):
        utc = datetime(2026,10,19,12,0,tzinfo=timezone.utc)
        rows = [
            (1,"US","TSMC ADR","TSMC 공급 계약","공식 발표에 계약 규모 미공개",utc),
            (2,"US","알파벳 Class A","구글 이슈","구글 발표 사실 확인",utc),
            (3,"US","팔란티어 테크놀로지스","제외 종목","표시하면 안 됨",utc),
            (4,"KR","삼성전자","반도체 계약","원문 검증",utc),
        ]
        fake = types.SimpleNamespace(connect=lambda *a,**k: FakeConn(rows))
        with patch.dict(sys.modules, {"psycopg": fake}):
            data = read_ai_issue_map("mock://db")
        self.assertEqual([x["headline"] for x in data[("US","TSM")]], ["TSMC 공급 계약"])
        self.assertEqual(data[("US","GOOGL")][0]["summary"], "구글 발표 사실 확인")
        self.assertEqual(data[("KR","005930")][0]["summary"], "원문 검증")
        self.assertEqual(sum(len(v) for v in data.values()), 3)

    def test_frontend_sidebar_never_calls_quote_or_rank(self):
        code = pathlib.Path("frontend/pages/watchlist/watchlist.js").read_text()
        for forbidden in ("/market/trading-value", "/analyze", "/api/quote",
                          "current_price", "change_pct", "fetchStockPrice"):
            self.assertNotIn(forbidden, code)
        self.assertIn("/api/fixed-stocks", code)


if __name__ == "__main__":
    unittest.main()
