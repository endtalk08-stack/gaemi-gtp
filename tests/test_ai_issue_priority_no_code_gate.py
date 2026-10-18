"""Offline regression: important news can reach AI with zero code issues.

No external network, Neon connections, or paid AI invocations.
"""
import sys
import pathlib
import unittest
from datetime import date, datetime, timezone, timedelta
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops"))
from staged_ai_sequential_batch import has_eligible_ai_news
from staged_ai_snapshot_integration import with_ai_issue_briefs
from staged_news_processed_store import _prefer_same_day_ai


class AIPrimaryTests(unittest.TestCase):
    def test_relevant_dated_news_even_with_zero_code_issues(self):
        rows = [{"title": "SpaceX launches new rocket", "description": "Detailed verified report",
                 "published_at": (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()}]
        self.assertTrue(has_eligible_ai_news(rows))
        self.assertFalse(has_eligible_ai_news([{"title": "Only title"}]))
        self.assertFalse(has_eligible_ai_news([{"title": "Text", "description": "No source date"}]))

    def test_recovery_reuses_ledger_and_source_bundle_without_new_ai_call(self):
        from staged_auto_ai_daily import _RECONCILE_DISPLAY_SQL
        self.assertIn("status='completed'", _RECONCILE_DISPLAY_SQL)
        self.assertIn("stock_ai_issue_sources_v1", _RECONCILE_DISPLAY_SQL)
        self.assertIn("'{_code_issue_briefs}'", _RECONCILE_DISPLAY_SQL)
        self.assertIn("'{_ai_issue_briefs}'", _RECONCILE_DISPLAY_SQL)
        self.assertIn("expires_at>now()", _RECONCILE_DISPLAY_SQL)
        self.assertNotIn("INSERT INTO public.news_ai_call_ledger", _RECONCILE_DISPLAY_SQL)
        self.assertNotIn("ELSE to_char(r.completed_at", _RECONCILE_DISPLAY_SQL)

    def test_code_issues_kept_when_ai_is_displayed(self):
        before = {"_news_status": "ok", "paired_news_items": [{"title": "SpaceX"}],
                  "issue_briefs": [{"headline": "코드", "stock_names": ["스페이스X"]}]}
        ai = [{"headline": "AI 핵심 재료", "summary": "분석", "tags": []}]
        after = with_ai_issue_briefs(before, ai, display_time="07:20",
                                     stock_names=["스페이스X"],
                                     exchange_day=date(2026,10,17))
        self.assertEqual(after["issue_briefs"][0]["headline"], "AI 핵심 재료")
        self.assertEqual(after["_code_issue_briefs"], before["issue_briefs"])
        self.assertEqual(after["_ai_exchange_day"], "2026-10-17")
        self.assertEqual(before["issue_briefs"][0]["headline"], "코드")

    def test_refresh_keeps_ai_and_new_code_separately(self):
        ai_brief = {"headline": "AI 핵심", "stock_names": ["스페이스X"],
                    "source_articles": [{"published_at": (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(),
                                         "url": "https://example.com/article", "source": "example.com"}]}
        old = {"_ai_exchange_day": "2026-10-17", "_ai_issue_briefs": [ai_brief]}
        fresh = {"issue_briefs": [{"headline": "새 코드", "stock_names": ["스페이스X"]}],
                 "paired_news_items": [{"title": "새 기사"}]}
        merged = _prefer_same_day_ai(fresh, old, "스페이스X", "2026-10-17")
        self.assertEqual([item["headline"] for item in merged["issue_briefs"]], ["AI 핵심"])
        self.assertTrue(merged["issue_briefs"][0]["time"])
        self.assertEqual(merged["issue_briefs"][0]["source_articles"][0]["url"], "https://example.com/article")
        self.assertEqual(merged["_code_issue_briefs"][0]["headline"], "새 코드")
        self.assertEqual(merged["paired_news_items"][0]["title"], "새 기사")

    def test_next_day_and_other_company_never_reuses_old_ai(self):
        old = {"_ai_exchange_day": "2026-10-17",
               "_ai_issue_briefs": [{"headline": "타사 AI", "stock_names": ["테슬라"]}]}
        original = {"issue_briefs": [{"headline": "코드", "stock_names": ["스페이스X"]}]}
        today = _prefer_same_day_ai(dict(original), old, "스페이스X", "2026-10-17")
        self.assertEqual(today["issue_briefs"], [])
        old[" _unused"] = 1
        yesterday = _prefer_same_day_ai(dict(original),
            {"_ai_exchange_day": "2026-10-16", "_ai_issue_briefs": [{
                "headline":"옛 AI","stock_names":["스페이스X"]}]},
            "스페이스X", "2026-10-17")
        self.assertEqual(yesterday["issue_briefs"], [])


if __name__ == "__main__":
    unittest.main()
