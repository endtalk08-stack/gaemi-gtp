"""No paid AI calls, no Naver calls, no Neon writes in these regression tests."""
import unittest
from unittest.mock import patch
from backend.analysis.news.stock_identity import (
    resolve_us_identity, news_snapshot_names, normalize_us_ticker,
)
from backend.analysis.news.catalog import canonical_us_news_name
from backend.services.stock_identity_store import register_us_ranking_instruments
from backend.services import market_issue_headlines
from backend.services import news_result


class IdentityTests(unittest.TestCase):
    def test_share_company_news_but_not_price_identity(self):
        a = resolve_us_identity("알파벳 Class A", "GOOGL.O")
        c = resolve_us_identity("알파벳 Class C", "GOOG.O")
        self.assertEqual(a["company_key"], c["company_key"])
        self.assertEqual(a["news_name"], "알파벳")
        self.assertEqual(c["news_name"], "알파벳")
        self.assertNotEqual(a["ticker"], c["ticker"])
        self.assertIn("알파벳 Class A", news_snapshot_names("알파벳 Class C", "GOOG.O"))
        self.assertEqual(canonical_us_news_name("알파벳 Class C"), "알파벳")
        self.assertEqual(canonical_us_news_name("알파벳 Class C", symbol="NVDA.O"), "알파벳 Class C")

    def test_known_ticker_english_and_korean_names(self):
        cases = [
            ("TSMC ADR", "TSM.N", "TSMC"),
            ("아마존닷컴", "AMZN.O", "아마존"),
            ("팔란티어 테크놀로지스", "PLTR.N", "팔란티어"),
            ("마벨 테크놀로지 그룹", "MRVL.O", "마벨 테크놀로지 그룹"),
            ("AMD(어드밴스드 마이크로 디바이시스)", "AMD.O", "AMD"),
            ("네비우스 그룹", "NBIS.O", "네비우스 그룹"),
        ]
        for name, ticker, expected in cases:
            with self.subTest(ticker=ticker):
                self.assertEqual(resolve_us_identity(name,ticker)["news_name"], expected)
        self.assertEqual(normalize_us_ticker("BRK.B"), "BRK.B")

    def test_unknown_ticker_never_steals_another_company(self):
        a = resolve_us_identity("알파벳 Class A", "AAPL.O")
        self.assertEqual(a["status"], "pending")
        self.assertEqual(a["news_name"], "알파벳 Class A")
        self.assertEqual(news_snapshot_names("알파벳 Class A", "AAPL.O"), ["알파벳 Class A"])
        unknown = resolve_us_identity("새로운 종목", "NEW.O")
        self.assertEqual(unknown["company_key"], "US:NEW")
        self.assertEqual(unknown["status"], "pending")

    def test_sidebar_can_read_same_company_briefs_once(self):
        with patch.object(market_issue_headlines, "_read_worker_briefs",
                          return_value={"알파벳 Class A": [{"headline":"뉴스"}]}) as read:
            value=market_issue_headlines.get_market_issue_headlines(
                "us", [{"name":"알파벳 Class C", "symbol":"GOOG.O"}])
        self.assertEqual(value["items"][0]["headline"],"뉴스")
        self.assertEqual(value["items"][0]["name"],"알파벳 Class C")
        self.assertIn("알파벳 Class A", read.call_args.args[1])

    def test_central_news_reads_canonical_when_no_row_is_present(self):
        def finder(name,**kwargs):
            return ({"issue_briefs":[],"paired_news_items":[{"title":"기사"}]}
                    if name=="알파벳 Class A" else None)
        with patch.object(news_result,"_read_worker_news_snapshot",side_effect=finder) as query:
            found=news_result.get_shared_stock_news_result("알파벳 Class C",market="미국")
        self.assertEqual(found["paired_news_items"][0]["title"],"기사")
        self.assertIn("알파벳 Class A",[x.args[0] for x in query.call_args_list])

    def test_registration_does_not_run_without_connection(self):
        with patch.dict("os.environ", {"NEWS_DATABASE_URL": ""}):
            self.assertEqual(register_us_ranking_instruments(
                [{"name":"신규", "symbol":"NEW.O"}]),0)


if __name__ == "__main__":
    unittest.main()
