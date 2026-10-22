import unittest
from unittest.mock import patch

from backend.services.news_feed import fetch_stock_news


class StockNewsQueryTests(unittest.TestCase):
    def setUp(self):
        self.official_patcher = patch(
            "backend.services.news_feed.official_company_news.fetch_company_news",
            return_value=[],
        )
        self.sec_patcher = patch(
            "backend.services.news_feed.sec_filings.fetch_recent_filings",
            return_value=[],
        )
        self.official_fetch = self.official_patcher.start()
        self.sec_fetch = self.sec_patcher.start()
        self.addCleanup(self.official_patcher.stop)
        self.addCleanup(self.sec_patcher.stop)

    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_us_stock_uses_all_company_aliases(self, fetch_queries):
        fetch_stock_news(
            "알파벳", market="미국", limit=20,
        )
        fetch_queries.assert_called_once()
        self.assertEqual(
            fetch_queries.call_args.args[0],
            ["알파벳", "GOOGL", "GOOG", "구글", "google", "alphabet"],
        )

    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_us_stock_restores_official_and_sec_sources(self, fetch_queries):
        fetch_stock_news("알파벳", market="미국", limit=20)
        self.official_fetch.assert_called_once()
        self.sec_fetch.assert_called_once()
        self.assertEqual(self.sec_fetch.call_args.args[1], "GOOGL")

    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_domestic_stock_keeps_existing_alias_cap(self, fetch_queries):
        fetch_stock_news(
            "SK하이닉스", market="국내", limit=20,
        )
        fetch_queries.assert_called_once()
        self.assertEqual(
            fetch_queries.call_args.args[0],
            ["SK하이닉스", "sk하이닉스", "하이닉스", "sk hynix"],
        )

    @patch("backend.services.news_feed._fetch_queries")
    def test_english_foreign_press_kept_for_us_stock(self, fetch_queries):
        fetch_queries.return_value = [
            {
                "title": "Alphabet signs a new technology agreement",
                "description": "Alphabet signed an agreement with a partner.",
                "url": "https://www.reuters.com/technology/alpha-agreement",
                "published_at": "",
                "source": "Reuters",
            },
            {
                "title": "CNBC reports on Google cloud investment",
                "description": "Google plans an investment in cloud infrastructure.",
                "url": "https://www.cnbc.com/2026/10/10/google-cloud.html",
                "published_at": "",
                "source": "CNBC",
            },
        ]
        result = fetch_stock_news(
            "알파벳", market="미국", limit=20,
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(
            {item["source"] for item in result}, {"Reuters", "CNBC"},
        )
        fetch_queries.assert_called_once()
 
    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_nebius_queries_use_verified_english_and_korean_aliases(self, fetch_queries):
        fetch_stock_news("네비우스 그룹", market="미국", limit=20)
        queries = fetch_queries.call_args.args[0]
        self.assertEqual(queries, ["네비우스 그룹", "NBIS", "네비우스", "Nebius", "Nebius Group"])
        self.assertEqual(self.sec_fetch.call_args.args[1], "NBIS")

    @patch("backend.services.news_feed._fetch_queries", return_value=[])
    def test_marvell_queries_use_verified_company_aliases(self, fetch_queries):
        fetch_stock_news("마벨 테크놀로지 그룹", market="미국", limit=20)
        queries = fetch_queries.call_args.args[0]
        self.assertEqual(queries, ["마벨 테크놀로지 그룹", "MRVL", "마벨", "Marvell", "Marvell Technology"])
        self.assertEqual(self.sec_fetch.call_args.args[1], "MRVL")

    @patch("backend.services.news_feed._fetch_queries")
    def test_nebius_real_headline_is_retained_without_keyword_fabrication(self, fetch_queries):
        fetch_queries.return_value = [{
            "title": "Nebius announces new data center investment",
            "description": "Nebius announces expansion and spending for new capacity.",
            "url": "https://example.org/nebius-announcement",
            "published_at": "",
            "source": "Example",
        }]
        news = fetch_stock_news("네비우스 그룹", market="미국", limit=20)
        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]["title"], "Nebius announces new data center investment")



class AlpacaNeonLinkTests(unittest.TestCase):
    """Alpaca is a US-only DigitalOcean provider, linked by Neon instrument symbol."""

    def _article(self, *, ticker="NVDA", url="https://www.benzinga.com/news/26/10/nvda"):
        import datetime
        published = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {
            "source_type": "alpaca_news", "provider": "alpaca",
            "provider_stock": "엔비디아", "provider_ticker": ticker,
            "provider_symbols": [ticker], "source": "benzinga",
            "title": "Nvidia announces new investment",
            "description": "NVIDIA announced a major infrastructure investment.",
            "published_at": published, "url": url, "link": url,
        }

    def test_us_merges_alpaca_with_naver_and_saves_using_neon_ticker(self):
        from backend.services import news_feed
        naver = {
            "title": "엔비디아 투자 발표", "description": "엔비디아 투자 확대 발표",
            "url": "https://example.org/naver", "link": "https://example.org/naver",
            "published_at": "", "source": "네이버",
        }
        with patch.object(news_feed, "_fetch_queries", return_value=[naver]), \
             patch.object(news_feed.official_company_news, "fetch_company_news", return_value=[]), \
             patch.object(news_feed.sec_filings, "fetch_recent_filings", return_value=[]), \
             patch.object(news_feed, "resolve_us_news_identity", return_value={
                 "ticker": "NVDA", "status": "verified"
             }), \
             patch.object(news_feed.alpaca_news, "is_configured", return_value=True), \
             patch.object(news_feed.alpaca_news, "fetch_stock_news",
                          return_value=[self._article()]) as alpaca, \
             patch.object(news_feed, "save_stock_articles", return_value=1) as save, \
             patch.dict("os.environ", {"GAEMIGTP_NEWS_WORKER": "1"}):
            result = fetch_stock_news("엔비디아", market="미국", limit=20)
        self.assertEqual({row["url"] for row in result},
                         {"https://example.org/naver", "https://www.benzinga.com/news/26/10/nvda"})
        self.assertEqual(alpaca.call_args.args[:2], ("엔비디아", "NVDA"))
        save.assert_called_once()
        self.assertEqual(save.call_args.args[0], "NVDA")
        a = next(row for row in result if row.get("source_type") == "alpaca_news")
        self.assertIn({"name": "엔비디아", "region": "미국"}, a["stocks"])

    def test_korean_stocks_never_request_alpaca(self):
        from backend.services import news_feed
        with patch.object(news_feed, "_fetch_queries", return_value=[]), \
             patch.object(news_feed.alpaca_news, "fetch_stock_news") as alpaca, \
             patch.object(news_feed.alpaca_news, "is_configured") as configured:
            self.assertEqual(fetch_stock_news("삼성전자", market="국내"), [])
        alpaca.assert_not_called()
        configured.assert_not_called()

    def test_alpaca_requires_exact_api_symbol(self):
        import datetime
        import json
        import os
        import types
        from backend.providers import alpaca_news
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size=-1):
                return json.dumps({"news": [
                    {"headline": "Relevant NVDA announcement", "summary": "Nvidia expands",
                     "symbols": ["NVDA"], "created_at": stamp, "content": "<p>Detail here</p>",
                     "url": "https://example.com/nvda"},
                    {"headline": "Wrong AAPL news", "summary": "Apple launches",
                     "symbols": ["AAPL"], "created_at": stamp,
                     "url": "https://example.com/apple"},
                ]}).encode()
        alpaca_news._CACHE.clear()
        with patch.dict(os.environ, {
            "GAEMIGTP_NEWS_WORKER": "1",
            "APCA_API_KEY_ID": "test-id",
            "APCA_API_SECRET_KEY": "test-secret",
        }), patch.object(alpaca_news.urllib.request, "urlopen", return_value=Response()) as opener:
            rows = alpaca_news.fetch_stock_news("엔비디아", "NVDA")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://example.com/nvda")
        self.assertEqual(rows[0]["description"], "Detail here")
        self.assertEqual(opener.call_args.args[0].get_header("Apca-api-key-id"), "test-id")

    def test_store_uses_existing_neon_instrument_and_article_symbol_link(self):
        import datetime
        import os
        import sys
        import types
        from backend.services import alpaca_news_store
        sql_calls = []
        class Cursor:
            def execute(self, sql, params=None):
                sql_calls.append((sql, params))
            def fetchall(self): return [("NVDA.O",)]
            def fetchone(self): return (42,)
            def __enter__(self): return self
            def __exit__(self, *args): return False
        class Conn:
            def cursor(self): return Cursor()
            def __enter__(self): return self
            def __exit__(self, *args): return False
        fake_psycopg = types.SimpleNamespace(connect=lambda *args, **kwargs: Conn())
        item = self._article()
        with patch.dict(os.environ, {
            "GAEMIGTP_NEWS_WORKER": "1", "NEWS_DATABASE_URL": "postgresql://test/db",
        }), patch.dict(sys.modules, {"psycopg": fake_psycopg}):
            count = alpaca_news_store.save_stock_articles("NVDA", [item])
        self.assertEqual(count, 1)
        self.assertTrue(any("public.market_instruments" in sql for sql, _ in sql_calls))
        self.assertTrue(any("public.news_article_symbols" in sql for sql, _ in sql_calls))
        self.assertTrue(any("public.news_articles" in sql for sql, _ in sql_calls))
        symbols = next(params for sql, params in sql_calls if "INSERT INTO public.news_article_symbols" in sql)
        self.assertEqual(symbols, (42, "NVDA.O"))


class SecMissingDisclosureDetailsTests(unittest.TestCase):
    """Pure SEC provider checks: no network, no new test module."""

    def test_form144_extracts_real_proposed_sale_fields(self):
        from backend.providers.sec_filings import _panel_form144_fields
        xml = """
        <edgarSubmission><formData><nameOfPersonForWhoseAccountTheSecuritiesAreToBeSold>
        Director A</nameOfPersonForWhoseAccountTheSecuritiesAreToBeSold>
        <securitiesInformation><securitiesClassTitle>Common Stock</securitiesClassTitle>
        <noOfUnitsSold>6500</noOfUnitsSold>
        <aggregateMarketValue>1200450.50</aggregateMarketValue>
        <approxSaleDate>10/19/2026</approxSaleDate></securitiesInformation>
        </formData></edgarSubmission>
        """
        fields = _panel_form144_fields(xml)
        values = {row["label"]: row["value"] for row in fields}
        self.assertEqual(values["매도 예정 주식 수"], "6500")
        self.assertEqual(values["예상 시장가치(USD)"], "1200450.50")
        self.assertEqual(values["매도 예정일"], "10/19/2026")

    def test_companyfacts_does_not_use_unrelated_or_ytd_quarter_values(self):
        from backend.providers.sec_filings import _panel_filing_metrics
        accession = "0001045810-26-000011"
        facts = {"facts": {"us-gaap": {
            "NetIncomeLoss": {"units": {"USD": [
                {"accn": accession, "form": "10-Q", "start": "2026-01-01",
                 "end": "2026-06-30", "val": 999},
                {"accn": "0001045810-26-000099", "form": "10-Q",
                 "start": "2026-04-01", "end": "2026-06-30", "val": 777},
                {"accn": accession, "form": "10-Q",
                 "start": "2026-04-01", "end": "2026-06-30", "val": 123},
            ]}}
        }}}
        rows = _panel_filing_metrics(facts, accession, "10-Q")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], 123)

    def test_non_sec_or_malformed_archive_url_rejected_before_request(self):
        from backend.providers.sec_filings import _panel_submission
        for url in (
            "https://attacker.example/Archives/edgar/data/1045810/000104581026000011/0001045810-26-000011-index.htm",
            "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000012/0001045810-26-000011-index.htm",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    _panel_submission(url)

if __name__ == "__main__":
    unittest.main()
