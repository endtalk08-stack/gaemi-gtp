"""Read-only DigitalOcean US issue dropout audit safety and classification tests."""
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

MODULE = Path(__file__).resolve().parents[1] / "ops/news-worker/audit-us-issue-dropout.py"
spec = importlib.util.spec_from_file_location("us_issue_audit", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def test_counts_issue_drop_without_claiming_article_body_failure(self):
        now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        result = audit.summarize_snapshot((
            "테슬라", now, now,
            [{"relation_type": "direct", "storyboard_keywords": ["로드스터"]},
             {"relation_type": "direct", "storyboard_keywords": []},
             {"relation_type": "mention_only", "storyboard_keywords": ["주식"]}],
            [], [], "ok",
        ))
        self.assertEqual(result["news"], 3)
        self.assertEqual(result["direct"], 2)
        self.assertEqual(result["direct_with_keyword"], 1)
        self.assertEqual(result["selected"], 0)
        self.assertEqual(result["issues"], 0)
        self.assertTrue(result["requires_rejection_trace"])
        self.assertNotIn("cause", result)

    def test_rejection_parser_distinguishes_body_source_and_material(self):
        samples = [
            '[news decision] ' + json.dumps({
                "stock": "테슬라", "stage": "rejected_after_body",
                "reason": "unverified_article_source", "source": "fetch_failed",
                "url": "https://example.com/private?token=SECRET",
            }, ensure_ascii=False),
            '[news decision] ' + json.dumps({
                "stock": "테슬라", "stage": "rejected_after_body",
                "reason": "no_supported_material_topic"}, ensure_ascii=False),
            '[news decision] ' + json.dumps({
                "stock": "테슬라", "stage": "rejected_before_body",
                "reason": "price_snapshot"}, ensure_ascii=False),
            '[news decision] ' + json.dumps({
                "stock": "엔비디아", "stage": "accepted_after_body"}, ensure_ascii=False),
            'arbitrary malformed line',
        ]
        counts = audit.parse_rejection_counts(samples, ["테슬라"])
        self.assertEqual(counts["테슬라"], {
            "rejected_after_body:unverified_article_source": 1,
            "rejected_after_body:no_supported_material_topic": 1,
            "rejected_before_body:price_snapshot": 1,
        })
        self.assertNotIn("SECRET", json.dumps(counts))

    def test_empty_or_missing_arrays_not_fail(self):
        now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        self.assertEqual(audit.summarize_snapshot(
            ("메타", now, now, None, "[]", [], "ok"))["issues"], 0)

    def test_without_database_config_never_connects(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                result = audit.main(["--stock", "테슬라"])
        self.assertEqual(result, 2)
        self.assertIn("NEWS_DATABASE_URL_NOT_CONFIGURED", stdout.getvalue())

    def test_sql_has_read_only_select_no_mutation(self):
        query = audit.READ_ONLY_SQL.upper()
        for forbidden in ("INSERT", "UPDATE ", "DELETE ", "TRUNCATE", "DROP ", "CREATE "):
            self.assertNotIn(forbidden, query)
        self.assertIn("NEWS_PROCESSED_SNAPSHOTS", query)


if __name__ == "__main__":
    unittest.main()
