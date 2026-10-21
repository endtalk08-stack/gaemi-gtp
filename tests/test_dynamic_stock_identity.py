"""No paid AI calls, no Naver calls, no Neon writes in these regression tests."""
import unittest
from datetime import datetime, timezone
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
            ("아이온큐", "IONQ.K", "아이온큐"),
            ("오라클", "ORCL.K", "오라클"),
            ("SK하이닉스 ADR", "SKHY.O", "SK하이닉스 ADR"),
            ("스페이스X", "SPCX.O", "스페이스X"),
        ]
        for name, ticker, expected in cases:
            with self.subTest(ticker=ticker):
                self.assertEqual(resolve_us_identity(name,ticker)["news_name"], expected)
        self.assertEqual(normalize_us_ticker("BRK.B"), "BRK.B")
        self.assertEqual(normalize_us_ticker("ORCL.K"), "ORCL")
        self.assertEqual(normalize_us_ticker("IONQ.K"), "IONQ")

    def test_unknown_ticker_never_steals_another_company(self):
        a = resolve_us_identity("알파벳 Class A", "AAPL.O")
        self.assertEqual(a["status"], "pending")
        self.assertEqual(a["news_name"], "알파벳 Class A")
        self.assertEqual(news_snapshot_names("알파벳 Class A", "AAPL.O"), ["알파벳 Class A"])
        for name, code in [("다른 회사", "ORCL.K"), ("다른 회사", "IONQ.K"),
                           ("다른 회사", "SKHY.O"), ("다른 회사", "SPCX.O")]:
            self.assertEqual(resolve_us_identity(name, code)["status"], "pending")
        unknown = resolve_us_identity("새로운 종목", "NEW.O")
        self.assertEqual(unknown["company_key"], "US:NEW")
        self.assertEqual(unknown["status"], "pending")

    def test_adr_and_space_news_do_not_cross_into_other_tickers(self):
        self.assertEqual(news_snapshot_names("SK하이닉스 ADR", "SKHY.O"), ["SK하이닉스 ADR"])
        self.assertEqual(news_snapshot_names("스페이스X", "SPCX.O"), ["스페이스X"])
        self.assertEqual(resolve_us_identity("SK하이닉스 ADR", "SPCX.O")["status"], "pending")
        self.assertEqual(resolve_us_identity("스페이스X", "SKHY.O")["status"], "pending")

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
            return ({"issue_briefs":[],"paired_news_items":[{"title":"기사", "published_at":datetime.now(timezone.utc).isoformat()}]}
                    if name=="알파벳 Class A" else None)
        with patch.object(news_result,"_read_worker_news_snapshot",side_effect=finder) as query:
            found=news_result.get_shared_stock_news_result("알파벳 Class C",market="미국")
        self.assertEqual(found["paired_news_items"][0]["title"],"기사")
        self.assertIn("알파벳 Class A",[x.args[0] for x in query.call_args_list])

    def test_snapshot_store_accepts_only_verified_same_company(self):
        import pathlib
        import sys
        ops_path = str(pathlib.Path(__file__).resolve().parents[1] / "ops")
        if ops_path not in sys.path:
            sys.path.insert(0, ops_path)
        if not pathlib.Path(ops_path, "staged_news_processed_store.py").exists():
            self.skipTest("DigitalOcean-only staged store; absent from Render source")
        from staged_news_processed_store import _same_stock_issue_briefs
        briefs = [
            {"headline": "알파벳", "stock_names": ["알파벳"]},
            {"headline": "구글", "stock_names": ["구글"]},
            {"headline": "엔비디아", "stock_names": ["엔비디아"]},
        ]
        retained = _same_stock_issue_briefs(briefs, "알파벳 Class A")
        self.assertEqual([b["headline"] for b in retained], ["알파벳", "구글"])
        self.assertEqual(_same_stock_issue_briefs(briefs, "TSMC ADR"), [])

    def test_cached_registry_expands_verified_search_without_renaming(self):
        from backend.services.news_identity_registry import resolve_us_news_identity
        registered = ({
            "ticker": "TSM", "label": "TSMC ADR", "news": "TSMC",
            "key": "US:TSM", "status": "verified",
        },)
        with patch("backend.services.news_identity_registry._registry", return_value=registered):
            result = resolve_us_news_identity("TSMC ADR")
        self.assertEqual((result["ticker"], result["news_name"]), ("TSM", "TSMC"))
        self.assertEqual(result["status"], "verified")
        self.assertIn("taiwan semiconductor", [x.casefold() for x in result["search_terms"]])
        self.assertIn("TSMC ADR", result["snapshot_names"])

    def test_company_share_classes_keep_original_snapshot_fallback(self):
        from backend.services.news_identity_registry import resolve_us_news_identity
        with patch("backend.services.news_identity_registry._registry", return_value=()):
            result = resolve_us_news_identity("알파벳 Class C")
        self.assertIn("알파벳 Class A", result["snapshot_names"])
        self.assertEqual(result["ticker"], "GOOG")

    def test_conflicting_ticker_never_cross_joins_stock_news(self):
        from backend.services.news_identity_registry import resolve_us_news_identity
        with patch("backend.services.news_identity_registry._registry", return_value=()):
            result = resolve_us_news_identity("알파벳 Class A", "AAPL.O")
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["search_terms"], ["알파벳 Class A"])
        self.assertEqual(result["snapshot_names"], ["알파벳 Class A"])

    def test_registration_does_not_run_without_connection(self):
        with patch.dict("os.environ", {"NEWS_DATABASE_URL": ""}):
            self.assertEqual(register_us_ranking_instruments(
                [{"name":"신규", "symbol":"NEW.O"}]),0)


if __name__ == "__main__":
    unittest.main()
