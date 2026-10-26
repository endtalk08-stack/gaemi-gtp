"""Offline contracts for append-only, cited US CODE issue history (no database)."""
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

module_path = Path(__file__).resolve().parents[1] / "ops" / "staged_news_processed_store.py"
spec = importlib.util.spec_from_file_location("staged_news_processed_store_history", module_path)
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class FakeCursor:
    def __init__(self, ticker="TSLA"):
        self.ticker = ticker
        self.saved = {}
        self.rowcount = 0

    def execute(self, sql, params):
        if "FROM public.market_instruments" in sql:
            self.rowcount = 1
            return
        assert "INSERT INTO public.news_issue_history" in sql
        ticker, company_key, stock_name, source_url, published, brief = params
        key = (ticker, source_url)
        self.rowcount = 0 if key in self.saved else 1
        self.saved.setdefault(key, dict(company_key=company_key, stock_name=stock_name,
                                        published_at=published, brief=brief))

    def fetchall(self):
        return [(self.ticker, "US:" + self.ticker)]


def brief(url, age_hours=1, title="테슬라 공급 계약"):
    published = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    return dict(headline=title, summary="원문으로 검증된 공급 계약", stock_names=["테슬라"],
                evidence_source="verified_article_body_title_only",
                source_articles=[{"url": url, "published_at": published.isoformat(),
                                  "source": "test"}])


def payload(briefs):
    return {"_title_only_revision": 3, "_code_fact_extraction_version": 3,
            "_code_issue_briefs": briefs}


class UsIssueHistoryContracts(unittest.TestCase):
    def setUp(self):
        psycopg = types.ModuleType("psycopg")
        types_mod = types.ModuleType("psycopg.types")
        json_mod = types.ModuleType("psycopg.types.json")
        json_mod.Jsonb = lambda value: value
        self.modules = patch.dict(sys.modules, {"psycopg": psycopg,
                          "psycopg.types": types_mod, "psycopg.types.json": json_mod})
        self.modules.start()
        self.identity = patch.object(store, "_same_stock_issue_briefs",
                                     side_effect=lambda items, name: list(items))
        self.identity.start()
        self.addCleanup(self.modules.stop)
        self.addCleanup(self.identity.stop)

    def test_reanalysis_zero_keeps_previous_events_and_no_duplicate(self):
        cur = FakeCursor()
        a = brief("https://example.org/tesla/one")
        self.assertEqual(store._archive_verified_us_code_issues(cur, "테슬라", payload([a])), 1)
        first = list(cur.saved.values())[0]["published_at"]
        self.assertEqual(store._archive_verified_us_code_issues(cur, "테슬라", payload([])), 0)
        self.assertEqual(store._archive_verified_us_code_issues(cur, "테슬라", payload([a])), 0)
        self.assertEqual(len(cur.saved), 1)
        self.assertEqual(list(cur.saved.values())[0]["published_at"], first)

    def test_new_article_appends_one_and_old_is_excluded(self):
        cur = FakeCursor()
        a = brief("https://example.org/tesla/one")
        b = brief("https://example.org/tesla/two", age_hours=2)
        old = brief("https://example.org/tesla/old", age_hours=25)
        self.assertEqual(store._archive_verified_us_code_issues(
            cur, "테슬라", payload([a, b, old])), 2)
        self.assertEqual(len(cur.saved), 2)

    def test_unknown_evidence_and_date_never_archived(self):
        cur = FakeCursor()
        invalid = brief("https://example.org/tesla/unverified")
        invalid["evidence_source"] = "original_unavailable"
        missing_date = brief("https://example.org/tesla/no-date")
        missing_date["source_articles"][0].pop("published_at")
        self.assertEqual(store._archive_verified_us_code_issues(
            cur, "테슬라", payload([invalid, missing_date])), 0)
        self.assertEqual(cur.saved, {})


if __name__ == "__main__":
    unittest.main()
