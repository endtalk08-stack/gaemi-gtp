"""Worker safety tests, running with the current repository's dependencies."""
import unittest
from unittest.mock import patch
from backend.news_worker import configured_stocks, process_stock
from backend.services.news_processed_store import source_fingerprint

class TestNewsWorkerSeparation(unittest.TestCase):
    def test_no_implicit_full_market_scan(self):
        with self.assertRaises(ValueError):
            configured_stocks("")

    def test_catalog_stock_names_only(self):
        self.assertEqual(configured_stocks("국내:삼성전자,국내:삼성전자,미국:엔비디아"),
                         [("국내","삼성전자"),("미국","엔비디아")])
        with self.assertRaises(ValueError):
            configured_stocks("미국:INVALID")

    def test_input_digest_order_independent(self):
        a = [{"title":"first","link":"one"},{"title":"second","link":"two"}]
        self.assertEqual(source_fingerprint(a),source_fingerprint(list(reversed(a))))
        self.assertNotEqual(source_fingerprint(a),source_fingerprint(a+[{"title":"new"}]))

    @patch("backend.news_worker.store.mark_checked")
    @patch("backend.news_worker.store.read_signature")
    @patch("backend.news_worker.store.save_snapshot")
    @patch("backend.news_worker.build_stock_news_result")
    @patch("backend.news_worker.fetch_stock_news")
    def test_unchanged_skips_analysis(self, fetch, analyze, save, signature, checked):
        fetch.return_value=[{"title":"same","link":"url"}]
        signature.return_value=source_fingerprint(fetch.return_value)
        self.assertEqual(process_stock("국내","삼성전자"),"unchanged")
        analyze.assert_not_called()
        save.assert_not_called()
        checked.assert_called_once()

    @patch("backend.news_worker.store.read_signature",return_value=None)
    @patch("backend.news_worker.store.save_snapshot")
    @patch("backend.news_worker.build_stock_news_result",return_value={"_news_status":"error"})
    @patch("backend.news_worker.fetch_stock_news",return_value=[])
    def test_failed_analysis_does_not_replace_good_data(self, fetch, analyze, save, signature):
        with self.assertRaises(RuntimeError):
            process_stock("국내","삼성전자")
        save.assert_not_called()

if __name__=="__main__":
    unittest.main()
