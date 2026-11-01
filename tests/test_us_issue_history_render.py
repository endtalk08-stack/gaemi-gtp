"""Offline contracts for Render's append-only issue-history display."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend.services import market_issue_headlines as sidebar
from backend.services import news_result as central


def brief(article, published):
    return {
        "headline": "검증된 CODE 재료", "summary": "원문에서 확인된 새로운 발표.",
        "evidence_source": "verified_article_body_title_only",
        "stock_names": ["테슬라"],
        "source_articles": [{
            "url": "https://source.example/" + article,
            "title": "원문 제목 " + article,
            "published_at": published.isoformat(),
            "source": "source.example",
        }],
    }


def empty_worker_snapshot():
    return {
        "_news_status": "ok", "issue_briefs": [], "_code_issue_briefs": [],
        "_title_only_revision": 3, "_code_fact_extraction_version": 3,
        "paired_news_items": [], "storyboard_news_items": [],
    }


class RenderUsIssueHistoryTests(unittest.TestCase):
    def test_reanalysis_zero_keeps_existing_issues_in_chat_and_orders_by_source_time(self):
        now = datetime.now(timezone.utc)
        older, newer = brief("older", now-timedelta(hours=3)), brief("newer", now-timedelta(hours=1))
        with patch.object(central, "resolve_us_news_identity", return_value={
                "snapshot_names": ["테슬라"], "ticker": "TSLA", "status": "verified"}), \
             patch.object(central, "_read_worker_news_snapshot",
                          return_value=empty_worker_snapshot()), \
             patch.object(central, "read_recent_us_code_issue_history",
                          return_value={"TSLA": [older, newer]}):
            result = central.get_shared_stock_news_result("테슬라", market="미국", symbol="TSLA")
        self.assertEqual([b["headline"] for b in result["issue_briefs"]],
                         ["원문 제목 newer", "원문 제목 older"])
        self.assertEqual(result["_news_status"], "ok")

    def test_24h_expired_source_does_not_reappear_in_chat(self):
        now = datetime.now(timezone.utc)
        expired = brief("stale", now-timedelta(hours=25))
        fresh = brief("fresh", now-timedelta(minutes=15))
        with patch.object(central, "resolve_us_news_identity", return_value={
                "snapshot_names": ["테슬라"], "ticker": "TSLA", "status": "verified"}), \
             patch.object(central, "_read_worker_news_snapshot",
                          return_value=empty_worker_snapshot()), \
             patch.object(central, "read_recent_us_code_issue_history",
                          return_value={"TSLA": [expired, fresh]}):
            result = central.get_shared_stock_news_result("테슬라", market="미국", symbol="TSLA")
        self.assertEqual(len(result["issue_briefs"]), 1)
        self.assertEqual(result["issue_briefs"][0]["headline"], "원문 제목 fresh")

    def test_sidebar_displays_latest_history_even_when_snapshot_has_no_issues(self):
        now = datetime.now(timezone.utc)
        rows = [brief("older", now-timedelta(hours=3)),
                brief("newer", now-timedelta(hours=1))]
        with patch.object(sidebar, "resolve_us_news_identity",
                          return_value={"snapshot_names": ["테슬라"]}), \
             patch.object(sidebar, "_read_worker_briefs", return_value={}), \
             patch.object(sidebar, "read_recent_us_code_issue_history",
                          return_value={"TSLA": rows}):
            result = sidebar.get_market_issue_headlines("us", [{"name": "테슬라", "symbol": "TSLA"}])
        self.assertEqual(result["items"][0]["headline"], "원문 제목 newer")
        self.assertEqual(result["items"][0]["status"], "ready")

    def test_conflicting_unverified_ticker_never_joins_other_company_history(self):
        with patch.object(central, "resolve_us_news_identity", return_value={
                "snapshot_names": ["테슬라"], "ticker": "", "status": "pending"}), \
             patch.object(central, "_read_worker_news_snapshot", return_value=None), \
             patch.object(central, "read_recent_us_code_issue_history") as archive_reader:
            result = central.get_shared_stock_news_result("테슬라", market="미국", symbol="NVDA")
        archive_reader.assert_not_called()
        self.assertEqual(result["_news_status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
