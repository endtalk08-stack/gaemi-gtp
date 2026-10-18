"""Offline sequential batch checks; no Groq or database calls."""
import importlib.util
import pathlib
import sys
import unittest
from datetime import date
from unittest.mock import Mock

OPS = pathlib.Path(__file__).resolve().parents[1] / "ops"
sys.path.insert(0, str(OPS))
spec = importlib.util.spec_from_file_location("staged_ai_sequential_batch", OPS / "staged_ai_sequential_batch.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SequentialBatchTests(unittest.TestCase):
    def test_one_stock_at_a_time_and_existing_connection(self):
        calls = []
        class Conn:
            def transaction(self):
                from contextlib import nullcontext
                return nullcontext()
        conn = Conn()
        stocks = [
            {"name": "엔비디아", "articles": [{"title": "a"}], "market": "US",
             "symbol": "NVDA", "exchange_day": date(2026, 10, 17)},
            {"name": "테슬라", "articles": [{"title": "b"}], "market": "US",
             "symbol": "TSLA", "exchange_day": date(2026, 10, 17)},
        ]
        def analyze(name, articles):
            calls.append(("analyze", name))
            return [{"headline": name, "summary": "본문", "tags": []}]
        def save(c, issues, **kwargs):
            self.assertIs(c, conn)
            self.assertIn("sources_by_issue", kwargs)
            calls.append(("save", kwargs["symbol"]))
            return [len(calls)]
        results = module.run_stock_batch(conn, stocks, analyze=analyze, save=save,
                                         reserve=lambda *a, **k: True,
                                         finish=lambda *a, **k: True)
        self.assertEqual(calls, [("analyze", "엔비디아"), ("save", "NVDA"),
                                 ("analyze", "테슬라"), ("save", "TSLA")])
        self.assertEqual([r["issue_count"] for r in results], [1, 1])

    def test_failed_stock_does_not_block_next(self):
        stocks = [
            {"name": n, "articles": [{"title": n}], "market": "US",
             "symbol": n, "exchange_day": date(2026, 10, 17)}
            for n in ("A", "B")
        ]
        def analyze(name, articles):
            if name == "A":
                raise RuntimeError("offline")
            return []
        results = module.run_stock_batch(type('Conn', (), {'transaction': lambda self: __import__('contextlib').nullcontext()})(), stocks, analyze=analyze, save=Mock(), reserve=lambda *a, **k: True, finish=lambda *a, **k: True)
        self.assertEqual([r["status"] for r in results], ["error", "ok"])
        self.assertEqual(results[0]["error_type"], "RuntimeError")
        self.assertEqual(results[0]["error_code"], "processing_error")

    def test_duplicate_reservation_skips_paid_call(self):
        from contextlib import nullcontext
        conn = type("Conn", (), {"transaction": lambda self: nullcontext()})()
        stock = {"name": "엔비디아", "articles": [{"title": "뉴스"}],
                 "market": "US", "symbol": "NVDA", "exchange_day": date(2026, 10, 17)}
        analyze, save, finish = Mock(), Mock(), Mock()
        results = module.run_stock_batch(
            conn, [stock], analyze=analyze, save=save,
            reserve=lambda *a, **k: False, finish=finish)
        self.assertEqual(results[0]["status"], "already_reserved")
        analyze.assert_not_called()
        save.assert_not_called()
        finish.assert_not_called()

    def test_reservation_happens_before_ai_call(self):
        from contextlib import nullcontext
        conn = type("Conn", (), {"transaction": lambda self: nullcontext()})()
        stock = {"name": "엔비디아", "articles": [{"title": "뉴스"}],
                 "market": "US", "symbol": "NVDA", "exchange_day": date(2026, 10, 17)}
        calls = []
        def reserve(*a, **k):
            calls.append("reserve")
            return True
        def analyze(*a):
            calls.append("analyze")
            return []
        def finish(*a, **k):
            calls.append("finish")
            return True
        result = module.run_stock_batch(
            conn, [stock], analyze=analyze, save=Mock(),
            reserve=reserve, finish=finish)
        self.assertEqual(calls, ["reserve", "analyze", "finish"])
        self.assertEqual(result[0]["status"], "ok")

    def test_no_articles_does_not_call_groq_or_save(self):
        stock = {"name": "A", "articles": [], "market": "US", "symbol": "A",
                 "exchange_day": date(2026, 10, 17)}
        analyze, save = Mock(), Mock()
        results = module.run_stock_batch(object(), [stock], analyze=analyze, save=save)
        analyze.assert_not_called()
        save.assert_not_called()
        self.assertEqual(results[0]["issue_count"], 0)


    def test_provider_error_records_only_http_status_and_preserves_guard(self):
        import urllib.error
        from contextlib import nullcontext
        connection = type("Conn", (), {"transaction": lambda self: nullcontext()})()
        finished = []
        def fake_analyze(*args):
            raise urllib.error.HTTPError(
                "https://redacted.example", 429, "Sensitive response", {}, None)
        result = module.run_stock_batch(connection, [{
            "name": "스페이스X", "symbol": "스페이스X",
            "market": "US", "exchange_day": date(2026, 10, 18),
            "articles": [{"title": "article"}],
        }], analyze=fake_analyze, save=Mock(),
            reserve=lambda *a, **k: True,
            finish=lambda *a, **kwargs: finished.append(kwargs) or True)[0]
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "http_429")
        self.assertEqual(finished[0]["failure_reason"], "http_429")
        self.assertEqual(finished[0]["failure_category"], "HTTPError")

    def test_invalid_response_reason_is_bounded(self):
        self.assertEqual(module._safe_failure_reason(ValueError("Invalid tags")), "invalid_issue_tags")
        self.assertEqual(module._safe_failure_reason(ValueError("secret provider text")), "validation_error")
        self.assertEqual(module._safe_failure_reason(ValueError("model_response_truncated")), "model_truncated")


if __name__ == "__main__":
    unittest.main()
