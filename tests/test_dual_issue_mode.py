"""Both stored article/AI channels can be selected without model calls or DB writes."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend.services.news_freshness import (
    clean_us_snapshot, issue_mode_for_question, normalize_issue_mode,
)
from backend.services import market_issue_headlines as sidebar


NOW = datetime.now(timezone.utc)


def brief(title, hours=1):
    return {
        "headline": title,
        "summary": title + " 원문에서 확인된 설명 세 문장을 보존한다.",
        "tags": ["원래키워드"],
        "source_articles": [{
            "url": "https://example.org/" + title.replace(" ", "-"),
            "published_at": (NOW - timedelta(hours=hours)).isoformat(),
        }],
    }


def source_snapshot(*, v3=True):
    return {
        "_title_only_revision": 3 if v3 else None,
        "_code_fact_extraction_version": 3 if v3 else 2,
        "_code_issue_briefs": [brief("코드 팩트 이슈")],
        "_ai_issue_briefs": [brief("AI 종합 이슈")],
        "issue_briefs": [brief("오래된 UI 기본값")],
    }


class DualIssueModesTest(unittest.TestCase):
    def test_auto_prefers_verified_code_but_keeps_ai(self):
        result = clean_us_snapshot(source_snapshot(), now=NOW)
        self.assertEqual([x["headline"] for x in result["issue_briefs"]], ["코드 팩트 이슈"])
        self.assertEqual([x["headline"] for x in result["issue_channels"]["ai"]], ["AI 종합 이슈"])
        self.assertEqual(result["issue_display_channel"] if "issue_display_channel" in result else result["_issue_display_channel"], "code")

    def test_explicit_ai_does_not_mutate_code_source(self):
        snapshot = source_snapshot()
        result = clean_us_snapshot(snapshot, now=NOW, issue_mode="ai")
        self.assertEqual([x["headline"] for x in result["issue_briefs"]], ["AI 종합 이슈"])
        self.assertEqual(result["issue_channels"]["code"][0]["tags"], ["원래키워드"])
        self.assertEqual(snapshot["issue_briefs"][0]["headline"], "오래된 UI 기본값")

    def test_explicit_code_stays_empty_when_no_verified_body(self):
        snapshot = source_snapshot(v3=False)
        result = clean_us_snapshot(snapshot, now=NOW, issue_mode="code")
        self.assertEqual(result["issue_briefs"], [])
        self.assertEqual(result["issue_channels"]["code"], [])
        self.assertEqual(len(result["issue_channels"]["ai"]), 1)
        self.assertEqual(clean_us_snapshot(snapshot, now=NOW)["issue_briefs"], [])

    def test_both_shows_two_without_loss_of_original_summaries(self):
        source = source_snapshot()
        result = clean_us_snapshot(source, now=NOW, issue_mode="both")
        self.assertEqual([x["headline"] for x in result["issue_briefs"]],
                         ["코드 팩트 이슈", "AI 종합 이슈"])
        for key in ("code", "ai"):
            self.assertEqual(result["issue_channels"][key][0]["tags"], ["원래키워드"])
            self.assertEqual(result["issue_channels"][key][0]["summary"],
                             source["_"+("code" if key == "code" else "ai")+"_issue_briefs"][0]["summary"])

    def test_freshness_applies_independently_to_each_channel(self):
        source = source_snapshot()
        source["_code_issue_briefs"] = [brief("오래된 팩트", 40)]
        result = clean_us_snapshot(source, now=NOW, issue_mode="both")
        self.assertEqual([x["headline"] for x in result["issue_briefs"]], ["AI 종합 이슈"])
        self.assertEqual(result["issue_channels"]["code"], [])

    def test_question_selection_and_sanitized_mode(self):
        self.assertEqual(issue_mode_for_question("엔비디아 왜 올랐어?"), "ai")
        self.assertEqual(issue_mode_for_question("테슬라 왜 하락했어?"), "ai")
        self.assertEqual(issue_mode_for_question("마이크론 이슈는 있어?"), "code")
        self.assertEqual(issue_mode_for_question("애플 최근 뉴스는?"), "code")
        self.assertEqual(issue_mode_for_question("이슈는 있어?", explicit="ai"), "ai")
        self.assertEqual(normalize_issue_mode("DROP TABLE"), "auto")
        self.assertEqual(normalize_issue_mode("BOTH"), "both")

    def test_sidebar_independent_switch_uses_one_worker_read(self):
        result = clean_us_snapshot(source_snapshot(), now=NOW)
        with patch.object(sidebar, "_read_worker_briefs", return_value={"테슬라": result}) as worker:
            row = [{"name": "테슬라", "symbol": "TSLA"}]
            self.assertEqual(sidebar.get_market_issue_headlines("us", row)["items"][0]["headline"], "코드 팩트 이슈")
            self.assertEqual(sidebar.get_market_issue_headlines("us", row, issue_mode="ai")["items"][0]["headline"], "AI 종합 이슈")
            self.assertEqual(sidebar.get_market_issue_headlines("us", row, issue_mode="code")["items"][0]["headline"], "코드 팩트 이슈")
            self.assertEqual(worker.call_count, 3)
            self.assertEqual(worker.call_args.args, ("us", ["테슬라"]))

    def test_domestic_path_is_not_altered(self):
        with patch.object(sidebar, "_read_worker_briefs", return_value={
            "삼성전자": {"issue_briefs": [{"headline": "원래 국내 뉴스"}]}
        }):
            got = sidebar.get_market_issue_headlines("kr",
                    [{"name": "삼성전자", "symbol": "005930"}], issue_mode="code")
            self.assertEqual(got["items"][0]["headline"], "원래 국내 뉴스")


if __name__ == "__main__":
    unittest.main()
