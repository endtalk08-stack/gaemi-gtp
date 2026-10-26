"""US Naver listing names must reach the news company without cross-ticker issues."""
import unittest
from unittest.mock import patch

from backend.analysis.news.catalog import canonical_us_news_name
from backend.services import market_issue_headlines, news_feed, news_result


class UsListingNewsIdentityTests(unittest.TestCase):
    def test_verified_naver_names_and_ticker_suffixes(self):
        cases = [
            ("알파벳 Class A", "GOOGL.O", "알파벳"),
            ("아마존닷컴", "AMZN.O", "아마존"),
            ("팔란티어 테크놀로지스", "PLTR.N", "팔란티어"),
            ("NVIDIA", "NVDA.O", "엔비디아"),
            ("Apple", "AAPL.O", "애플"),
            ("Microsoft", "MSFT.O", "마이크로소프트"),
        ]
        for name, symbol, canonical in cases:
            with self.subTest(name=name):
                self.assertEqual(canonical_us_news_name(name, symbol=symbol), canonical)
        self.assertEqual(canonical_us_news_name("NVIDIA", symbol="AAPL.O"), "NVIDIA")
        self.assertEqual(canonical_us_news_name("알파벳 Class A", symbol="GOOG.O"), "알파벳 Class A")
        self.assertEqual(canonical_us_news_name("미등록 신규상장사", symbol="NEW.O"), "미등록 신규상장사")
        self.assertEqual(canonical_us_news_name("삼성전자", symbol="005930"), "삼성전자")

    @patch.object(news_feed.sec_filings, "fetch_recent_filings", return_value=[])
    @patch.object(news_feed.official_company_news, "fetch_company_news", return_value=[])
    @patch.object(news_feed, "_fetch_queries", return_value=[])
    def test_provider_queries_for_naver_alphabet(self, query, official, sec):
        news_feed.fetch_stock_news("알파벳 Class A", market="미국", limit=20)
        queries = query.call_args.args[0]
        self.assertIn("GOOGL", queries)
        self.assertIn("google", queries)
        self.assertIn("alphabet", queries)
        self.assertEqual(official.call_args.args[0], "알파벳")
        self.assertEqual(sec.call_args.args[:2], ("알파벳", "GOOGL"))

    @patch.object(news_feed.sec_filings, "fetch_recent_filings", return_value=[])
    @patch.object(news_feed.official_company_news, "fetch_company_news", return_value=[])
    @patch.object(news_feed, "_fetch_queries", return_value=[])
    def test_provider_queries_for_amazon_and_palantir(self, query, official, sec):
        for source, canonical, ticker in [
            ("아마존닷컴", "아마존", "AMZN"),
            ("팔란티어 테크놀로지스", "팔란티어", "PLTR"),
        ]:
            with self.subTest(stock=source):
                news_feed.fetch_stock_news(source, market="미국", limit=20)
                self.assertIn(ticker, query.call_args.args[0])
                self.assertEqual(sec.call_args.args[:2], (canonical, ticker))

    @patch.object(news_feed, "_fetch_queries", return_value=[])
    def test_domestic_query_unchanged(self, query):
        with patch.object(news_feed.official_company_news, "fetch_company_news", return_value=[]), \
             patch.object(news_feed.sec_filings, "fetch_recent_filings", return_value=[]):
            news_feed.fetch_stock_news("삼성전자", market="국내", limit=20)
        self.assertEqual(query.call_args.args[0], ["삼성전자", "samsung electronics"])

    def test_sidebar_reads_existing_us_alias_without_renaming_row(self):
        captured = {}
        def worker(market, names):
            captured["worker_names"] = names
            return {"엔비디아": {"issue_briefs": [{
                "headline": "엔비디아 AI 뉴스 재료",
                "summary": "원문 근거",
                "source_articles": [{"url": "https://source.example/verified", "title": "엔비디아 AI 뉴스 재료"}],
            }]}}
        with patch.object(market_issue_headlines, "_read_worker_briefs", side_effect=worker):
            result = market_issue_headlines.get_market_issue_headlines("us", [
                {"name": "NVIDIA", "symbol": "NVDA.O"},
                {"name": "알파벳 Class A", "symbol": "GOOGL.O"},
            ])
        self.assertEqual(result["items"][0]["name"], "NVIDIA")
        self.assertEqual(result["items"][0]["headline"], "엔비디아 AI 뉴스 재료")
        self.assertEqual(result["items"][1]["headline"], "")
        self.assertEqual(result["items"][1]["status"], "unavailable")
        self.assertIn("엔비디아", captured["worker_names"])
        self.assertIn("알파벳", captured["worker_names"])

    def test_sidebar_rejects_mismatched_ticker(self):
        with patch.object(market_issue_headlines, "_read_worker_briefs", return_value={"엔비디아": [{"headline": "타종목 제목"}]}) as worker:
            out = market_issue_headlines.get_market_issue_headlines(
                "us", [{"name": "NVIDIA", "symbol": "AAPL.O"}])
        self.assertEqual(out["items"][0]["headline"], "")
        self.assertEqual(worker.call_args.args[1], ["NVIDIA"])

    def test_sidebar_kr_uses_only_original_name(self):
        with patch.object(market_issue_headlines, "_read_worker_briefs", return_value={}) as worker:
            out = market_issue_headlines.get_market_issue_headlines(
                "kr", [{"name": "삼성전자", "symbol": "005930"}])
        self.assertEqual(worker.call_args.args[1], ["삼성전자"])
        self.assertEqual(out["items"][0]["headline"], "")

    def test_central_reader_uses_existing_us_snapshot_alias_when_exact_missing(self):
        # US display only accepts source-dated code-fact briefs within 24 hours.
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        published = datetime.now(timezone.utc).isoformat()
        article = {"published_at": published, "url": "https://example.org/nvidia-news",
                   "source": "Example"}
        found = []
        def worker(name, **kwargs):
            found.append(name)
            if name == "엔비디아":
                brief = {"headline": "서버의 기존 이슈", "summary": "확인된 내용",
                         "source_articles": [article]}
                return {"issue_briefs": [brief], "_code_issue_briefs": [brief],
                        "_code_fact_extraction_version": 3,
                        "_title_only_revision": 3}
            return None
        with patch.object(news_result, "_read_worker_news_snapshot", side_effect=worker):
            result = news_result.get_shared_stock_news_result("NVIDIA", market="미국", limit=50)
        self.assertEqual(found, ["NVIDIA", "엔비디아"])
        self.assertEqual(result["issue_briefs"][0]["headline"], "서버의 기존 이슈")
        self.assertEqual(result["issue_briefs"][0]["time"], datetime.now(ZoneInfo("Asia/Seoul")).strftime("%H:%M"))
        self.assertEqual(result["issue_briefs"][0]["source_articles"][0]["published_at"], published)

    def test_no_worker_result_does_not_run_render_collection_or_write(self):
        """Missing worker output must never start Render news or reuse its old store."""
        for stock, market in [("삼성전자", "국내"), ("테슬라", "미국")]:
            with self.subTest(stock=stock), \
                 patch.object(news_result, "_read_worker_news_snapshot", return_value=None) as snapshot, \
                 patch.object(news_result, "build_stock_news_result", side_effect=AssertionError("Render collected news")):
                result = news_result.get_shared_stock_news_result(stock, market=market)
            self.assertEqual(snapshot.call_count, 1)
            self.assertEqual(result["issue_briefs"], [])
            self.assertEqual(result["paired_news_items"], [])
            self.assertEqual(result["_news_status"], "unavailable")

    def test_worker_result_is_not_overwritten_by_render_legacy_store(self):
        worker_result = {
            "issue_briefs": [{"headline": "DigitalOcean 이슈", "summary": "기사 근거"}],
            "paired_news_items": [], "storyboard_news_items": [], "keyword_storyboard": [],
        }
        with patch.object(news_result, "_read_worker_news_snapshot", return_value=worker_result), \
             patch.object(news_result, "build_stock_news_result", side_effect=AssertionError("Render collected news")):
            result = news_result.get_shared_stock_news_result("삼성전자", market="국내")
        self.assertEqual(result["issue_briefs"][0]["headline"], "DigitalOcean 이슈")

    def test_sidebar_only_reads_worker_and_never_render_legacy_store(self):
        with patch.object(market_issue_headlines, "_read_worker_briefs", return_value={
            "삼성전자": [{"headline": "DigitalOcean 이슈", "summary": "기사 근거"}],
        }) as read_worker:
            result = market_issue_headlines.get_market_issue_headlines(
                "kr", [{"name": "삼성전자", "symbol": "005930"}])
        self.assertEqual(read_worker.call_args.args, ("kr", ["삼성전자"]))
        self.assertEqual(result["items"][0]["headline"], "DigitalOcean 이슈")


if __name__ == "__main__":
    unittest.main()
