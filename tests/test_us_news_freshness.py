"""Read-only Render regression tests: US sidebar and chat share 24h citations."""
import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from backend.services.news_freshness import clean_us_snapshot
from backend.services import news_result


NOW = datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc)


def ts(hours):
    return (NOW - timedelta(hours=hours)).isoformat()


def brief(title, hours):
    return {
        "headline": title, "summary": "AI가 정리한 기사", "tags": ["#AI"],
        "stock_names": ["테슬라"], "time": "09:15",
        "source_articles": [{
            "published_at": ts(hours), "source": "newsroom",
            "url": "https://example.org/" + title
        }]
    }


class RenderFreshnessTests(unittest.TestCase):
    def test_two_day_old_code_fact_hidden_despite_recent_snapshot_write(self):
        payload = {
            "_code_fact_extraction_version": 2,
            "_code_issue_briefs": [brief("old", 49), brief("fresh", 1)],
            "issue_briefs": [brief("old", 49)],
            "_ai_exchange_day": "2026-10-18",
            "paired_news_items": [
                {"title": "old article", "published_at": ts(49)},
                {"title": "fresh article", "published_at": ts(1)},
            ],
        }
        view = clean_us_snapshot(payload, now=NOW)
        self.assertEqual([x["headline"] for x in view["issue_briefs"]], ["fresh"])
        self.assertEqual([x["title"] for x in view["paired_news_items"]], ["fresh article"])
        self.assertEqual(view["issue_briefs"][0]["source_articles"][0]["source"], "newsroom")
        self.assertEqual(view["issue_briefs"][0]["source_articles"][0]["url"],
                         "https://example.org/fresh")
        self.assertEqual(payload["issue_briefs"][0]["headline"], "old")

    def test_legacy_snapshot_without_new_version_is_not_displayed(self):
        payload = {"issue_briefs": [{"headline": "old deterministic",
                                    "reaction_at": ts(1), "stock_names": ["테슬라"]}]}
        self.assertEqual(clean_us_snapshot(payload, now=NOW)["issue_briefs"], [])

    def test_one_issue_with_mixed_dates_shows_only_recent_citations(self):
        fresh, old = brief("fresh", 1), brief("old", 49)
        mixed = {**fresh, "source_articles": old["source_articles"] + fresh["source_articles"]}
        cleaned = clean_us_snapshot({"_code_fact_extraction_version": 2,
                                     "_code_issue_briefs": [mixed]}, now=NOW)
        self.assertEqual(len(cleaned["issue_briefs"]), 1)
        self.assertEqual(len(cleaned["issue_briefs"][0]["source_articles"]), 1)

    def test_bad_or_future_article_dates_are_not_fabricated(self):
        payload = {"_code_fact_extraction_version": 2,
                   "_code_issue_briefs": [
            {"headline": "undated", "source_articles": [{"url": "https://example.org/x"}]},
            brief("future", -4),
        ], "paired_news_items": [
            {"title": "unknown", "published_at": ""},
            {"title": "future", "published_at": ts(-2)},
        ]}
        cleaned = clean_us_snapshot(payload, now=NOW)
        self.assertEqual(cleaned["issue_briefs"], [])
        self.assertEqual(cleaned["paired_news_items"], [])

    def test_ai_channel_never_overrides_code_channel(self):
        snapshot = {"_code_fact_extraction_version": 2,
                    "_code_issue_briefs": [brief("기사에서 추출한 이슈", 1)],
                    "_ai_issue_briefs": [brief("옛날 AI 분석", 1)],
                    "issue_briefs": [brief("옛날 AI 분석", 1)]}
        view = clean_us_snapshot(snapshot, now=NOW)
        self.assertEqual([x["headline"] for x in view["issue_briefs"]], ["기사에서 추출한 이슈"])

    def test_code_brief_requires_verified_fresh_article(self):
        invalid = {**brief("근거 없는 키워드", 1),
                   "source_articles": [{"url": "https://example.org/missing"}]}
        view = clean_us_snapshot({"_code_fact_extraction_version": 2,
                                  "_code_issue_briefs": [invalid]}, now=NOW)
        self.assertEqual(view["issue_briefs"], [])

    def test_central_chat_reads_same_guarded_code_channel(self):
        payload = {"_news_status": "ok",
                   "_code_fact_extraction_version": 2,
                   "_code_issue_briefs": [brief("fresh", 1), brief("stale", 49)],
                   "_ai_issue_briefs": [brief("outdated AI", 1)],
                   "issue_briefs": [brief("stale", 49)]}
        with patch.object(news_result, "resolve_us_news_identity",
                          return_value={"snapshot_names": ["테슬라"]}), patch.object(
            news_result, "_read_worker_news_snapshot", return_value=payload):
            result = news_result.get_shared_stock_news_result("테슬라", market="미국")
        self.assertEqual([x["headline"] for x in result["issue_briefs"]], ["fresh"])


if __name__ == "__main__":
    unittest.main()
