"""Render sidebar reads existing DigitalOcean snapshots only."""
import unittest
from unittest.mock import patch

from backend.services import market_issue_headlines as subject


class MarketIssueHeadlineTests(unittest.TestCase):
    def test_existing_worker_brief_is_displayed_without_news_processing(self):
        items = [{"name": "삼성전자", "symbol": "005930"}]
        briefs = [{"headline": "AI 반도체 이슈", "summary": "확인된 뉴스",
                   "stock_names": ["삼성전자"], "tags": ["AI반도체"]}]
        with patch.object(subject, "_read_worker_briefs",
                          return_value={"삼성전자": briefs}) as reader:
            result = subject.get_market_issue_headlines("kr", items)
        self.assertEqual(result["items"][0]["status"], "ready")
        self.assertEqual(result["items"][0]["headline"], "AI 반도체")
        self.assertFalse(result["pending"])
        reader.assert_called_once_with("kr", ["삼성전자"])

    def test_missing_worker_brief_is_not_generated_or_saved(self):
        items = [{"name": "삼성SDI", "symbol": "006400"}]
        with patch.object(subject, "_read_worker_briefs", return_value={}) as reader:
            result = subject.get_market_issue_headlines("kr", items)
        self.assertEqual(result["items"][0]["status"], "unavailable")
        self.assertEqual(result["items"][0]["headline"], "")
        self.assertFalse(result["pending"])
        reader.assert_called_once()

    def test_twenty_rows_have_one_worker_snapshot_read(self):
        items = [{"name": f"종목{i}", "symbol": f"{i:06d}"} for i in range(20)]
        with patch.object(subject, "_read_worker_briefs", return_value={}) as reader:
            result = subject.get_market_issue_headlines("kr", items)
        self.assertEqual(len(result["items"]), 20)
        self.assertTrue(all(row["status"] == "unavailable" for row in result["items"]))
        reader.assert_called_once()

    def test_one_bad_ranked_symbol_does_not_blank_other_nineteen(self):
        items = [{"name": f"종목{i}", "symbol": f"{i:06d}"} for i in range(20)]
        items[7] = {"name": "형식오류", "symbol": "INVALID.SYMBOL"}
        briefs = [{"headline": "공급 계약 이슈", "summary": "확인된 뉴스"}]
        with patch.object(subject, "_read_worker_briefs",
                          return_value={"종목0": briefs, "종목19": briefs}) as reader:
            result = subject.get_market_issue_headlines("kr", items, skip_invalid=True)
        self.assertEqual(len(result["items"]), 20)
        self.assertEqual(result["items"][0]["headline"], "공급 계약")
        self.assertEqual(result["items"][7]["headline"], "")
        self.assertEqual(result["items"][7]["status"], "invalid")
        self.assertEqual(result["items"][19]["headline"], "공급 계약")
        self.assertEqual(result["items"][19]["symbol"], "000019")
        names = reader.call_args.args[1]
        self.assertEqual(len(names), 19)
        self.assertNotIn("형식오류", names)

    def test_invalid_ranked_row_retains_position_and_never_reads_fake_identity(self):
        items = [
            {"name": "삼성전자", "symbol": "005930"},
            {"name": "", "symbol": None},
            {"name": "삼성SDI", "symbol": "006400"},
        ]
        briefs = [{"headline": "반도체 계약 이슈"}]
        with patch.object(subject, "_read_worker_briefs",
                          return_value={"삼성전자": briefs}) as reader:
            rows = subject.get_market_issue_headlines("kr", items, skip_invalid=True)["items"]
        self.assertEqual([row["status"] for row in rows], ["ready", "invalid", "unavailable"])
        self.assertEqual([row["headline"] for row in rows], ["반도체 계약", "", ""])
        reader.assert_called_once_with("kr", ["삼성전자", "삼성SDI"])

    def test_all_invalid_rank_rows_do_not_query_db(self):
        with patch.object(subject, "_read_worker_briefs") as reader:
            result = subject.get_market_issue_headlines(
                "kr", [{"name": "없는 종목", "symbol": "bad"}], skip_invalid=True,
            )
        reader.assert_not_called()
        self.assertEqual(result["items"][0]["headline"], "")

    def test_strict_external_requests_remain_strict(self):
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [
                    {"name": "삼성전자", "symbol": "005930"},
                    {"name": "형식오류", "symbol": "INVALID.SYMBOL"},
                ],
            )
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [], skip_invalid=True,
            )
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [{"name": "정상", "symbol": "005930"}] * 21,
                skip_invalid=True,
            )

    def test_bad_symbol_and_oversized_list_rejected(self):
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines("kr", [{"name": "SK", "symbol": "NVDA"}])
        with self.assertRaises(ValueError):
            subject.get_market_issue_headlines(
                "kr", [{"name": "x", "symbol": "005930"}] * 21,
            )


    def test_us_cited_code_issue_visible_without_price_reason(self):
        from datetime import datetime, timezone
        from backend.services.news_freshness import clean_us_snapshot
        now = datetime.now(timezone.utc)
        snapshot = clean_us_snapshot({
            "price_reason": None,
            "_code_fact_extraction_version": 3,
            "_title_only_revision": 3,
            "issue_briefs": [{"headline": "규칙이 만든 옛 재료"}],
            "_ai_issue_briefs": [{"headline": "오래된 AI"}],
            "_code_issue_briefs": [{
                "headline": "반도체 수요 확대",
                "summary": "기사에서 뽑은 사실",
                "source_articles": [{
                    "url": "https://source.example/story",
                    "source": "source.example",
                    "published_at": now.isoformat(),
                }],
            }],
        }, now=now)
        with patch.object(subject, "resolve_us_news_identity",
                          return_value={"snapshot_names": ["엔비디아"]}), \
             patch.object(subject, "_read_worker_briefs",
                          return_value={"엔비디아": snapshot}):
            result = subject.get_market_issue_headlines(
                "us", [{"name": "엔비디아", "symbol": "NVDA"}]
            )
        self.assertEqual(result["items"][0]["headline"], "반도체 수요 확대")
        self.assertEqual(result["items"][0]["status"], "ready")

    def test_us_no_stale_or_uncited_code_material_fallback(self):
        from datetime import datetime, timedelta, timezone
        from backend.services.news_freshness import clean_us_snapshot
        now = datetime.now(timezone.utc)
        snapshot = clean_us_snapshot({
            "price_reason": None,
            "issue_briefs": [{"headline": "옛 규칙 재료"}],
            "_code_fact_extraction_version": 3,
            "_title_only_revision": 3,
            "_code_issue_briefs": [{
                "headline": "하루 지난 코드 재료",
                "summary": "이미 지난 기사",
                "source_articles": [{
                    "url": "https://source.example/stale",
                    "source": "source.example",
                    "published_at": (now - timedelta(hours=25)).isoformat(),
                }],
            }],
        }, now=now)
        with patch.object(subject, "resolve_us_news_identity",
                          return_value={"snapshot_names": ["테슬라"]}), \
             patch.object(subject, "_read_worker_briefs",
                          return_value={"테슬라": snapshot}):
            result = subject.get_market_issue_headlines(
                "us", [{"name": "테슬라", "symbol": "TSLA"}]
            )
        self.assertEqual(result["items"][0]["status"], "unavailable")
        self.assertEqual(result["items"][0]["headline"], "")

    def test_us_ai_only_snapshot_never_displays_ai_as_code(self):
        from datetime import datetime, timezone
        from backend.services.news_freshness import clean_us_snapshot
        now = datetime.now(timezone.utc)
        snapshot = clean_us_snapshot({
            "issue_briefs": [{"headline": "구 AI 헤드라인"}],
            "_ai_issue_briefs": [{
                "headline": "구 AI 헤드라인",
                "source_articles": [{"published_at": now.isoformat(),
                                     "url": "https://example.org/old"}],
            }],
        }, now=now)
        with patch.object(subject, "resolve_us_news_identity",
                          return_value={"snapshot_names": ["마이크론 테크놀로지"]}), patch.object(
            subject, "_read_worker_briefs",
            return_value={"마이크론 테크놀로지": snapshot}):
            result = subject.get_market_issue_headlines(
                "us", [{"name": "마이크론 테크놀로지", "symbol": "MU"}]
            )
        self.assertEqual(result["items"][0]["headline"], "")
        self.assertEqual(result["items"][0]["status"], "unavailable")

    def test_sidebar_removes_only_trailing_issue_word(self):
        self.assertEqual(subject._sidebar_title("사업 확대 이슈"), "사업 확대")
        self.assertEqual(subject._sidebar_title("공급 계약 이슈  "), "공급 계약")
        self.assertEqual(subject._sidebar_title("이슈 분석 및 전망"), "이슈 분석 및 전망")

    def test_us_unverified_original_is_hidden_in_code_sidebar_and_chat(self):
        from datetime import datetime, timezone
        from backend.services.news_freshness import clean_us_snapshot
        now = datetime.now(timezone.utc)
        source = {"url": "https://example.org/news", "published_at": now.isoformat()}
        raw = {
            "_title_only_revision": 3,
            "_code_fact_extraction_version": 3,
            "_code_issue_briefs": [
                {"headline": "국제유가 급등 이슈", "summary": "원문 확인 불가",
                 "evidence_source": "original_unavailable", "source_articles": [source]},
                {"headline": "공급 계약 이슈", "summary": "원문에서 확인한 실제 문장.",
                 "evidence_source": "verified_article_body_title_only", "source_articles": [source]},
            ],
            "_ai_issue_briefs": [],
        }
        filtered = clean_us_snapshot(raw, now=now)
        self.assertEqual(len(filtered["issue_briefs"]), 1)
        self.assertEqual(filtered["issue_briefs"][0]["headline"], "공급 계약 이슈")
        self.assertEqual(len(filtered["issue_channels"]["code"]), 1)
        self.assertEqual(len(raw["_code_issue_briefs"]), 2, "database source must remain unchanged")
        with patch.object(subject, "resolve_us_news_identity",
                          return_value={"snapshot_names": ["스페이스X"]}), \
             patch.object(subject, "_read_worker_briefs",
                          return_value={"스페이스X": filtered}):
            result = subject.get_market_issue_headlines(
                "us", [{"name": "스페이스X", "symbol": "SPACEX"}]
            )
        self.assertEqual(result["items"][0]["headline"], "공급 계약")
        only_unavailable = clean_us_snapshot({
            **raw, "_code_issue_briefs": raw["_code_issue_briefs"][:1]
        }, now=now)
        self.assertEqual(only_unavailable["issue_briefs"], [])
        self.assertEqual(subject._first_ai_headline(only_unavailable), "")

    def test_us_ai_headline_does_not_invent_evidence(self):
        self.assertEqual(subject._first_ai_headline({"issue_briefs": [
            {"headline": "출처 없는 제목", "summary": "텍스트"}
        ]}), "")
        self.assertEqual(subject._first_ai_headline({"issue_briefs": [
            {"headline": "공식 공급 계약", "summary": "내용",
             "source_articles": [{"url": "https://source.example/official"}]}
        ]}), "공식 공급 계약")


if __name__ == "__main__":
    unittest.main()
