"""Offline checks for preserving existing verified US CODE issues on refresh."""
import pathlib
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

OPS = pathlib.Path(__file__).resolve().parents[1] / "ops"
sys.path.insert(0, str(OPS))
import staged_news_processed_store as store


def make_brief(headline, url):
    published = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    return {
        "headline": headline,
        "summary": "Verified original news content",
        "stock_names": ["테슬라"],
        "evidence_source": "verified_article_body_title_only",
        "source_articles": [{"url": url, "published_at": published}],
    }


class MemoryCursor:
    def __init__(self, previous):
        self.previous = previous
        self.saved = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        if "INSERT INTO public.news_processed_snapshots" in sql:
            self.saved = params[-1]

    def fetchone(self):
        return (self.previous,) if self.previous is not None else None


class MemoryConnection:
    def __init__(self, previous):
        self.cursor_obj = MemoryCursor(previous)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_obj


class PreserveExistingCodeIssuesTests(unittest.TestCase):
    def save(self, previous, current):
        conn = MemoryConnection({"_code_issue_briefs": previous})
        json_module = types.ModuleType("psycopg.types.json")
        json_module.Jsonb = lambda payload: payload
        with patch.object(store, "_connect", return_value=conn), patch.dict(
            sys.modules, {"psycopg": types.ModuleType("psycopg"),
                          "psycopg.types": types.ModuleType("psycopg.types"),
                          "psycopg.types.json": json_module}
        ):
            store.save_snapshot(
                "테슬라", market="미국", limit=50, storyboard_limit=3,
                display_timezone="Asia/Seoul", fingerprint="offline-test",
                result={"_news_status": "ok", "issue_briefs": [],
                        "_code_issue_briefs": current}
            )
        self.assertIsNotNone(conn.cursor_obj.saved)
        return conn.cursor_obj.saved["_code_issue_briefs"]

    def test_existing_issues_survive_zero_issue_reanalysis(self):
        original = make_brief("A", "https://source.example/a")
        saved = self.save([original], [])
        self.assertEqual([brief["headline"] for brief in saved], ["A"])
        self.assertEqual(saved[0]["source_articles"], original["source_articles"])

    def test_new_issue_is_added_without_losing_existing(self):
        old = make_brief("A", "https://source.example/a")
        new = make_brief("B", "https://source.example/b")
        saved = self.save([old], [new])
        self.assertEqual({brief["headline"] for brief in saved}, {"A", "B"})
        self.assertEqual(len(saved), 2)

    def test_same_article_is_not_duplicated(self):
        old = make_brief("A", "https://source.example/a")
        new_copy = make_brief("A copy", "https://source.example/a")
        saved = self.save([old], [new_copy])
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["headline"], "A")


if __name__ == "__main__":
    unittest.main()
