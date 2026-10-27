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
    def _render_issue_view(self, payload):
        """Mirror the actual chat path: freshness filter then display shaping."""
        return news_result._sanitize_news_display_briefs(
            clean_us_snapshot(payload, now=NOW), market="미국"
        )

    def test_two_day_old_code_fact_hidden_despite_recent_snapshot_write(self):
        payload = {
            "_code_fact_extraction_version": 3,
            "_title_only_revision": 3,
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
        cleaned = clean_us_snapshot({"_code_fact_extraction_version": 3, "_title_only_revision": 3,
                                     "_code_issue_briefs": [mixed]}, now=NOW)
        self.assertEqual(len(cleaned["issue_briefs"]), 1)
        self.assertEqual(len(cleaned["issue_briefs"][0]["source_articles"]), 1)

    def test_bad_or_future_article_dates_are_not_fabricated(self):
        payload = {"_code_fact_extraction_version": 3, "_title_only_revision": 3,
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
        snapshot = {"_code_fact_extraction_version": 3, "_title_only_revision": 3,
                    "_code_issue_briefs": [brief("기사에서 추출한 이슈", 1)],
                    "_ai_issue_briefs": [brief("옛날 AI 분석", 1)],
                    "issue_briefs": [brief("옛날 AI 분석", 1)]}
        view = clean_us_snapshot(snapshot, now=NOW)
        self.assertEqual([x["headline"] for x in view["issue_briefs"]], ["기사에서 추출한"])

    def test_code_brief_requires_verified_fresh_article(self):
        invalid = {**brief("근거 없는 키워드", 1),
                   "source_articles": [{"url": "https://example.org/missing"}]}
        view = clean_us_snapshot({"_code_fact_extraction_version": 3, "_title_only_revision": 3,
                                  "_code_issue_briefs": [invalid]}, now=NOW)
        self.assertEqual(view["issue_briefs"], [])

    def test_verified_three_sentence_summary_and_original_tags_are_untouched(self):
        summary = "마이크론은 새 제도를 발표했다. 성과급은 내년부터 지급된다. 지급액은 실적에 연동된다."
        item = {**brief("마이크론, 이익연동 성과급 도입", 1),
                "summary": summary, "tags": ["이익연동성과급"],
                "evidence_source": "verified_article_body_title_only"}
        result = clean_us_snapshot({
            "_code_fact_extraction_version": 3,
            "_title_only_revision": 3,
            "_code_issue_briefs": [item],
            "_ai_issue_briefs": [brief("구 AI 분석", 1)],
        }, now=NOW)
        self.assertEqual(len(result["issue_briefs"]), 1)
        self.assertEqual(result["issue_briefs"][0]["summary"], summary)
        self.assertEqual(result["issue_briefs"][0]["tags"], ["이익연동성과급"])
        self.assertEqual(result["issue_briefs"][0]["headline"], "마이크론, 이익연동 성과급 도입")

    def test_tesla_uses_evidenced_original_article_title_not_generic_label(self):
        summary = (
            "미국 전기차 업체 테슬라가 자율주행 기술과 에너지저장 사업의 성장 가능성에 힘입어 월가의 관심을 받고 있다. "
            "UBS는 테슬라의 목표주가를 기존 391달러에서 425달러로 높였다. "
            "그러나 투자의견은 중립을 유지해 신중한 접근을 주문했다. "
            "네 번째 문장은 나오면 안 된다."
        )
        title = "테슬라 자율주행·에너지 사업에 기대…UBS, 목표주가 425달러로 상향"
        item = {**brief("기사 주요 내용", 1), "summary": summary,
                "source_articles": [{**brief("x", 1)["source_articles"][0],
                                     "title": title}]}
        payload = {"_title_only_revision": 3, "_code_fact_extraction_version": 3,
                   "_code_issue_briefs": [item]}
        out = self._render_issue_view(payload)["issue_briefs"][0]
        self.assertEqual(out["headline"], title)
        self.assertEqual(out["summary"], summary)
        self.assertEqual(payload["_code_issue_briefs"][0]["summary"], summary)

    def test_stored_article_text_is_not_rewritten_by_display(self):
        snippet = (
            "호주 예약금 반환…테슬라 판매 취소 이미지 확대보기 "
            "쇼핑몰에 테슬라 차량이 전시돼 있다. "
            "사진=로이터 테슬라가 사이버트럭의 현지 출시를 취소했다. "
            "예약금은 모두 반환할 예정이다. "
            "생산 계획도 전면 철회했다. "
            "이 문장은 네 번째이므로 보이면 안 된다."
        )
        item = {**brief("테슬라, 현지 출시 취소", 1), "summary": snippet}
        out = self._render_issue_view({"_title_only_revision": 3,
            "_code_fact_extraction_version": 3, "_code_issue_briefs": [item]})["issue_briefs"][0]
        self.assertEqual(out["summary"], snippet)
        self.assertEqual(out["headline"], "테슬라, 현지 출시 취소")

    def test_recent_source_title_survives_unavailable_body_and_keywords(self):
        item = {**brief("실제 기사 제목", 1), "summary": "", "tags": [],
                "source_articles": [{**brief("x", 1)["source_articles"][0],
                                     "title": "실제 기사 제목"}]}
        out = self._render_issue_view({"_title_only_revision": 3,
            "_code_fact_extraction_version": 3, "_code_issue_briefs": [item]})["issue_briefs"]
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["headline"], "실제 기사 제목")
        self.assertEqual(out[0]["summary"], "")
        self.assertEqual(out[0]["tags"], [])

    def test_display_does_not_blank_stored_text_based_on_punctuation(self):
        index = (
            "“주차 맡기고 올라가세요” ... 현대위아 주차로봇 [단독] "
            "테슬라 추격 현대차 ... 엔비디아 기술책임자 영입 "
            "현대차 기본급 제시 ... 타이어값 인상 ..."
        )
        item = {**brief("기사 주요 내용", 1), "summary": index}
        payload = {"_title_only_revision": 3, "_code_fact_extraction_version": 3,
                   "_code_issue_briefs": [item]}
        self.assertEqual(self._render_issue_view(payload)["issue_briefs"][0]["summary"], index)
        self.assertEqual(payload["_code_issue_briefs"][0]["summary"], index)

    def test_nvda_generic_heading_recovers_original_verified_source_title(self):
        summary = (
            "엔비디아 최고경영자 젠슨 황이 엔스케일에 데이터센터 건설을 촉구했다. "
            "엔스케일의 데이터센터 구축 지연에 신속한 대응을 주문했다."
        )
        title = "젠슨 황, AI 데이터센터 지연에 경고…엔스케일 인프라 확충 시험대"
        item = {**brief("기사 주요 내용", 1), "summary": summary,
                "source_articles": [{**brief("x", 1)["source_articles"][0],
                                     "title": title}]}
        out = self._render_issue_view({"_title_only_revision": 3,
            "_code_fact_extraction_version": 3, "_code_issue_briefs": [item]})["issue_briefs"][0]
        self.assertEqual(out["headline"], title)

    def test_v3_without_verified_source_does_not_display_saved_ai(self):
        saved_ai = brief("이미 저장된 AI 뉴스", 1)
        view = clean_us_snapshot({
            "_code_fact_extraction_version": 3,
            "_title_only_revision": 3,
            "_code_issue_briefs": [],
            "_ai_issue_briefs": [saved_ai],
        }, now=NOW)
        self.assertEqual(view["issue_briefs"], [])
        self.assertEqual(view["_issue_display_channel"], "unavailable")
        self.assertEqual([b["headline"] for b in view["issue_channels"]["ai"]], ["이미 저장된 AI 뉴스"])

    def test_old_code_version_is_never_misrepresented_as_verified_body(self):
        result = clean_us_snapshot({
            "_code_fact_extraction_version": 2,
            "_code_issue_briefs": [brief("자른 기사 설명", 1)],
        }, now=NOW)
        self.assertEqual(result["issue_briefs"], [])

    def test_central_chat_reads_same_guarded_code_channel(self):
        actual_now = datetime.now(timezone.utc)
        def recent_brief(title, hours):
            return {"headline": title, "summary": "테슬라의 사업 계획이 발표됐다.",
                    "source_articles": [{
                "published_at": (actual_now - timedelta(hours=hours)).isoformat(),
                "url": "https://example.org/" + title,
            }]}
        payload = {"_news_status": "ok",
                   "_code_fact_extraction_version": 3,
                   "_title_only_revision": 3,
                   "_code_issue_briefs": [recent_brief("fresh", 1), recent_brief("stale", 49)],
                   "_ai_issue_briefs": [recent_brief("outdated AI", 1)],
                   "issue_briefs": [recent_brief("stale", 49)]}
        with patch.object(news_result, "resolve_us_news_identity",
                          return_value={"snapshot_names": ["테슬라"]}), patch.object(
            news_result, "_read_worker_news_snapshot", return_value=payload):
            result = news_result.get_shared_stock_news_result("테슬라", market="미국")
        self.assertEqual([x["headline"] for x in result["issue_briefs"]], ["fresh"])


    def test_us_recent_code_issues_display_latest_three_only(self):
        payload = {
            "_title_only_revision": 3,
            "_code_fact_extraction_version": 3,
            "_code_issue_briefs": [brief(f"issue-{i}", i) for i in range(1, 6)],
        }
        result = clean_us_snapshot(payload, now=NOW)
        self.assertEqual(len(result["issue_briefs"]), 3)
        self.assertEqual(len(result["issue_channels"]["code"]), 5)

    def test_original_article_titles_are_kept_over_generated_labels_and_keywords(self):
        summary = (
            "미국 기업들의 순이익이 증가할 것으로 전망됐다. "
            "전체 이익 증가분이 일부 기업에 집중됐다. "
            "시장 관계자들은 기업 실적 전망을 주목했다."
        )
        first = {
            "headline": "AI 반도체", "summary": summary,
            "tags": ["#AI반도체"],
            "source_articles": [{
                "url": "https://example.org/first",
                "title": "기사 원제목 첫 번째",
            }],
        }
        second = {
            "headline": "기사 주요 내용", "summary": summary,
            "tags": [],
            "source_articles": [{
                "url": "https://example.org/second",
                "title": "기사 원제목 두 번째",
            }],
        }
        third = {
            "headline": "이미 저장된 이슈 제목", "summary": summary,
            "tags": [],
            "source_articles": [{"url": "https://example.org/third"}],
        }
        payload = {
            "issue_briefs": [first, second, third],
            "storyboard_news_items": [
                {"url": "https://example.org/first", "storyboard_keywords": ["30%급증"]},
                {"url": "https://example.org/second", "storyboard_keywords": ["30%증가"]},
            ],
        }
        result = news_result._sanitize_news_display_briefs(payload, market="미국")
        self.assertEqual(
            [issue["headline"] for issue in result["issue_briefs"]],
            ["기사 원제목 첫 번째", "기사 원제목 두 번째", "이미 저장된 이슈 제목"],
        )
        self.assertEqual(len(result["issue_briefs"]), 3)

    def test_central_keywords_reuse_worker_article_keywords_only(self):
        item = {
            "headline": "기사 주요 내용",
            "summary": (
                "테슬라는 신규 공장을 증설한다고 발표했다. "
                "생산 시설은 내년부터 가동할 예정이다."
            ),
            "tags": ["AI반도체"],
            "source_articles": [{
                "url": "https://example.org/tesla-plant",
                "title": "테슬라, 공급 계약 체결",
            }],
        }
        result = news_result._sanitize_news_display_briefs({
            "issue_briefs": [item],
            "storyboard_news_items": [{
                "url": "https://example.org/tesla-plant",
                "article_keywords": ["양산개시", "생산확대", "공장건설", "초과키워드"],
                "storyboard_keywords": ["공급계약"],
            }],
        }, market="미국")
        self.assertEqual(result["issue_briefs"][0]["headline"], "테슬라, 공급 계약 체결")
        self.assertEqual(result["issue_briefs"][0]["tags"], ["양산개시", "생산확대", "공장건설"])
        self.assertEqual(len(result["issue_briefs"]), 1)

    def test_central_preserves_worker_issue_tags_when_article_lookup_is_missing(self):
        item = {
            "headline": "기존 제목",
            "summary": "테슬라는 신규 공장을 증설한다고 발표했다.",
            "tags": ["공장증설"],
            "source_articles": [{"url": "https://example.org/no-title"}],
        }
        result = news_result._sanitize_news_display_briefs(
            {"issue_briefs": [item]}, market="미국"
        )
        self.assertEqual(result["issue_briefs"][0]["headline"], "기존 제목")
        self.assertEqual(result["issue_briefs"][0]["tags"], ["공장증설"])
        self.assertEqual(len(result["issue_briefs"]), 1)

    def test_central_keywords_match_each_article_url_not_selection_order(self):
        first = {
            "headline": "첫 기사", "summary": "첫 기사 본문입니다.",
            "source_articles": [{"url": "https://example.org/first"}],
        }
        second = {
            "headline": "두 번째 기사", "summary": "두 번째 기사 본문입니다.",
            "source_articles": [{"url": "https://example.org/second"}],
        }
        result = news_result._sanitize_news_display_briefs({
            "issue_briefs": [first, second],
            "storyboard_news_items": [
                {"url": "https://example.org/second", "article_keywords": ["임상3상"]},
                {"url": "https://example.org/first", "article_keywords": ["30%급증", "수익성개선"]},
            ],
        }, market="미국")
        self.assertEqual([x["tags"] for x in result["issue_briefs"]],
                         [["30%급증", "수익성개선"], ["임상3상"]])

if __name__ == "__main__":
    unittest.main()

