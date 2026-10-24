"""Selected sidebar rows reuse the existing processed market menu results."""
import unittest
from unittest.mock import patch

from backend.services import market_rankings as rankings


class MarketSelectionContextTests(unittest.TestCase):
    def setUp(self):
        rankings._MARKET_RESULTS.clear()

    def test_four_menus_share_verified_stock_selection_without_another_fetch(self):
        kr = {"items": [{"itemCode": "005930", "price": {
            "itemName": "삼성전자", "marketType": "KOSPI",
            "krx": {"currentPrice": "234000", "changeRate": "-6.59",
                    "tradingValue": "5916362000000"}
        }}]}
        us = {"items": [{"itemCode": "NVDA.O", "price": {
            "itemName": "엔비디아", "symbolCode": "NVDA", "currentPrice": "225.78",
            "changeRate": "+2.50", "tradingValue": "3600000000",
            "sectorName": "반도체"
        }}]}
        kiwoom_saved = [{"rank": 1, "name": "엔비디아", "symbol": "NVDA",
                         "analysis_symbol": "NVDA", "industry": "반도체",
                         "price": 210.96, "change_pct": -0.59}]
        with (
            patch.object(rankings, "get_stock_industries", return_value={}) as industry,
            patch.object(rankings, "fetch_kr_popular_ranking_raw", return_value=kr) as kr_pop,
            patch.object(rankings, "fetch_kr_trading_value_ranking_raw", return_value=kr) as kr_val,
            patch.object(rankings, "fetch_us_popular_ranking_raw", return_value=us) as us_pop,
            patch.object(rankings, "_read_kiwoom_us_value_rows", return_value=kiwoom_saved) as us_val,
        ):
            kr_popular = rankings.build_kr_popular_result()
            kr_value = rankings.build_kr_trading_value_result()
            us_popular = rankings.build_us_popular_result()
            us_value = rankings.build_us_trading_value_result()
            for menu in ("popular", "value"):
                selected_kr = rankings.get_market_selection("kr", menu, "005930", stock="삼성전자")
                selected_us = rankings.get_market_selection("us", menu, "NVDA" if menu == "value" else "NVDA.O", stock="엔비디아")
                self.assertEqual(selected_kr["industry"], None)
                self.assertEqual(selected_kr["trading_value"], 5916362000000.0)
                self.assertEqual(selected_us["industry"], "반도체")
                self.assertEqual(rankings.analysis_ticker_for_selection(selected_kr), "005930.KS")
                self.assertEqual(rankings.analysis_ticker_for_selection(selected_us), "NVDA")
                self.assertEqual(selected_kr["market"], "kr")
                self.assertEqual(selected_us["currency"], "USD")
        for provider in (kr_pop, kr_val, us_pop, us_val):
            provider.assert_called_once()
        self.assertEqual(industry.call_count, 3)
        self.assertEqual(kr_popular[0]["name"], kr_value[0]["name"])
        self.assertEqual(us_popular[0]["name"], us_value[0]["name"])

    def test_kiwoom_neon_read_keeps_verified_auto_identity(self):
        import sys
        from unittest.mock import MagicMock
        records = [
            (i, "NVDA" if i == 1 else "SYM" + str(i),
             "엔비디아" if i == 1 else "종목" + str(i),
             210.96, -0.59, 120000.0, 1000, "반도체",
             "US:NVDA" if i == 1 else "US:SYM" + str(i),
             "엔비디아" if i == 1 else "종목" + str(i), "verified")
            for i in range(1, 21)
        ]
        psycopg = MagicMock()
        cursor = psycopg.connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = records
        with patch.dict(sys.modules, {"psycopg": psycopg}), patch.dict(
            rankings.os.environ, {"NEWS_DATABASE_URL": "dummy-neon"}, clear=False
        ):
            rows = rankings.build_us_trading_value_result()
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["company_key"], "US:NVDA")
        self.assertEqual(rows[0]["news_name"], "엔비디아")
        self.assertEqual(rows[0]["identity_status"], "verified")
        self.assertEqual(rows[0]["price"], 210.96)
        self.assertEqual(rankings.get_market_selection("us", "value", "NVDA")["company_key"], "US:NVDA")
        query = cursor.execute.call_args.args[0]
        self.assertIn("i.company_key", query)
        self.assertIn("i.identity_status", query)
        self.assertIn("JOIN public.market_instruments", query)

    def test_sidebar_worker_issue_uses_only_trusted_auto_identity(self):
        from backend.services import market_issue_headlines as headlines
        record = {
            "rank": 6, "name": "메타 플랫폼스(페이스북)",
            "symbol": "META", "company_key": "US:META",
            "news_name": "메타", "identity_status": "verified",
        }
        with patch.object(headlines, "_read_worker_briefs", return_value={
            "메타": [{"headline": "메타 분기 실적 발표", "summary": "실적"}]
        }) as reader:
            trusted = headlines.get_market_issue_headlines(
                "us", [record], trusted_kiwoom_identity=True
            )
            names = reader.call_args.args[1]
        self.assertIn("메타", names)
        self.assertEqual(trusted["items"][0]["status"], "ready")
        with patch.object(headlines, "_read_worker_briefs", return_value={
            "메타": [{"headline": "메타 분기 실적 발표", "summary": "실적"}]
        }) as reader:
            untrusted = headlines.get_market_issue_headlines("us", [record])
            names = reader.call_args.args[1]
        self.assertNotIn("메타", names)
        self.assertEqual(untrusted["items"][0]["headline"], "")
        with patch.object(headlines, "_read_worker_briefs", return_value={
            "메타": [{"headline": "메타 분기 실적 발표", "summary": "실적"}]
        }) as reader:
            pending = headlines.get_market_issue_headlines(
                "us", [{**record, "identity_status": "review"}],
                trusted_kiwoom_identity=True,
            )
            names = reader.call_args.args[1]
        self.assertNotIn("메타", names)
        self.assertEqual(pending["items"][0]["headline"], "")

    def test_kosdaq_market_type_overrides_name_guessing(self):
        kr = {"items": [{"itemCode": "247540", "price": {
            "itemName": "에코프로비엠", "marketType": "KOSDAQ",
            "krx": {"currentPrice": "100000"}
        }}]}
        with patch.object(rankings, "get_stock_industries", return_value={}), patch.object(
            rankings, "fetch_kr_popular_ranking_raw", return_value=kr,
        ):
            rankings.build_kr_popular_result()
        selected = rankings.get_market_selection("kr", "popular", "247540", "에코프로비엠")
        self.assertEqual(rankings.analysis_ticker_for_selection(selected), "247540.KQ")

    def test_wrong_market_menu_stock_code_or_name_is_rejected(self):
        rankings._remember_market_result("us", "popular", [{
            "name": "엔비디아", "symbol": "NVDA.O", "price": 200.0,
        }])
        self.assertIsNone(rankings.get_market_selection("kr", "popular", "NVDA.O"))
        self.assertIsNone(rankings.get_market_selection("us", "value", "NVDA.O"))
        self.assertIsNone(rankings.get_market_selection("us", "popular", "AAPL.O"))
        self.assertIsNone(rankings.get_market_selection("us", "popular", "NVDA.O", "테슬라"))
        self.assertIsNone(rankings.get_market_selection("us", "popular", "../bad"))
        self.assertIsNone(rankings.get_market_selection("us", "popular", "NVDA.O", ""))
        self.assertEqual(rankings.get_market_selection("us", "popular", "NVDA.O", "엔비디아")["price"], 200.0)

    def test_cached_menu_comparison_reuses_same_rows_without_source_calls(self):
        with patch.object(rankings, "fetch_us_popular_ranking_raw") as fetch:
            rankings._remember_market_result("us", "popular", [
                {"name": "엔비디아", "symbol": "NVDA.O", "rank": 1, "price": 225.78},
                {"name": "테슬라", "symbol": "TSLA.O", "rank": 2, "price": 401.0},
            ])
            rows = rankings.get_market_menu_rows("us", "popular")
            self.assertEqual(len(rows), 2)
            self.assertEqual([r["symbol"] for r in rows], ["NVDA.O", "TSLA.O"])
            rows[0]["price"] = 0
            self.assertEqual(rankings.get_market_menu_rows("us", "popular")[0]["price"], 225.78)
            self.assertEqual(rankings.get_market_menu_rows("kr", "popular"), [])
            fetch.assert_not_called()

    def test_change_sort_matches_visible_order_and_preserves_source_rank(self):
        rankings._remember_market_result("us", "popular", [
            {"name": "A", "symbol": "A.O", "rank": 1, "change_pct": 1.0},
            {"name": "B", "symbol": "B.O", "rank": 2, "change_pct": 10.0},
            {"name": "C", "symbol": "C.O", "rank": 3, "change_pct": 10.0},
            {"name": "D", "symbol": "D.O", "rank": 4, "change_pct": None},
        ])
        rows = rankings.get_market_menu_rows("us", "popular", sort="change_pct")
        self.assertEqual([row["symbol"] for row in rows], ["B.O", "C.O", "A.O", "D.O"])
        self.assertEqual([row["display_rank"] for row in rows], [1, 2, 3, 4])
        self.assertEqual([row["rank"] for row in rows], [2, 3, 1, 4])
        self.assertEqual([row["symbol"] for row in rankings.get_market_menu_rows("us", "popular")],
                         ["A.O", "B.O", "C.O", "D.O"])

    def test_older_menu_result_expires_without_fetching(self):
        with patch.object(rankings.time, "monotonic", return_value=100.0):
            rankings._remember_market_result("kr", "popular", [{
                "name": "삼성전자", "symbol": "005930",
            }])
        with patch.object(rankings.time, "monotonic", return_value=100.0 + rankings._SELECTION_TTL):
            self.assertIsNone(rankings.get_market_selection("kr", "popular", "005930"))

    def test_missing_exchange_does_not_guess_kospi_for_kosdaq(self):
        self.assertIsNone(rankings.analysis_ticker_for_selection({
            "market": "kr", "symbol": "247540", "market_type": "",
        }))
        self.assertIsNone(rankings.analysis_ticker_for_selection(None))


if __name__ == "__main__":
    unittest.main()
