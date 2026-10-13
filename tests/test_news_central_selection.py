"""Central-only stock relevance and distinct-event selection regression tests."""

import unittest
from unittest.mock import patch

from backend.analysis.news.storyboard import select_keyword_storyboard_news
from backend.services.news_result import (
    _central_direct_article,
    _central_stock_mentioned,
    build_stock_news_result,
)


class CentralNewsSelectionTests(unittest.TestCase):
    def article(self, key, title, body, keyword="공급계약", score=80):
        return {
            "title": title,
            "description": body,
            "url": f"https://example.org/{key}",
            "published_at": "2026-10-14T05:00:00+09:00",
            "storyboard_time": "05:00",
            "storyboard_keywords": [keyword],
            "article_keywords": [keyword],
            "storyboard_keyword": keyword,
            "article_keyword_details": [{"label": keyword, "source": "title"}],
            "analysis_relevance_tier": 3,
            "analysis_event_strength": 2,
            "relation_type": "direct",
            "flow_score": score,
            "flow_score_breakdown": {"direct_stock": 35},
        }

    def with_body(self, article):
        return dict(article, _central_checked_body=article["description"])

    def test_stock_aliases_and_false_substrings(self):
        for phrase in ("삼성전자는", "삼전은", "삼전이", "삼전의"):
            self.assertTrue(_central_stock_mentioned(phrase, "삼성전자"), phrase)
        for phrase in ("삼전동 주민", "삼전로", "메타플래닛", "기아차"):
            stock = "메타" if "메타" in phrase else "삼성전자" if "삼전" in phrase else "기아"
            self.assertFalse(_central_stock_mentioned(phrase, stock), phrase)
        self.assertTrue(_central_stock_mentioned("SK하이닉스가 계약했다.", "SK하이닉스"))
        self.assertFalse(_central_stock_mentioned("SK하이닉스가 계약했다.", "삼성전자"))

    def test_title_followed_by_anaphora_even_in_second_sentence(self):
        title = {"title": "삼성전자 평택 공장 증설"}
        texts = (
            "생산시설 확대 소식이 전해졌다. 회사는 평택 공장 증설을 결정했다고 밝혔다.",
            "생산시설 확대 소식이 전해졌다. 이 회사는 투자금액도 공개했다.",
            "동사는 반도체 공장 투자를 확대했다.",
        )
        for body in texts:
            self.assertTrue(_central_direct_article(title, body, "삼성전자"), body)

    def test_unrelated_news_is_rejected(self):
        a = {"title": "삼성전자 투자 관련 최신 소식"}
        self.assertFalse(_central_direct_article(a, "영국 의회는 새 세금을 의결했다.", "삼성전자"))
        self.assertFalse(_central_direct_article(
            {"title": "반도체 업계 주요 소식"},
            "영국 의회는 새 세금을 의결했다. 삼성전자도 언급됐다.",
            "삼성전자",
        ))
        self.assertFalse(_central_direct_article(
            {"title": "SK하이닉스 증설"},
            "SK하이닉스는 이천 공장을 확장했다.", "삼성전자",
        ))

    def test_generic_headline_explicit_company_in_first_sentence(self):
        self.assertTrue(_central_direct_article(
            {"title": "반도체 공장 증설 추진"},
            "삼성전자는 평택에 생산시설을 확장했다. 투자를 계속한다.",
            "삼성전자",
        ))

    def test_same_event_reports_collapse_to_one(self):
        title = "삼성전자 평택 공장 증설 규모 확대"
        a = self.with_body(self.article("1", title, "삼성전자는 평택 공장 증설을 발표했다. 생산량을 확대한다."))
        b = self.with_body(self.article("2", title, "삼성전자는 평택 공장 증설을 발표했다. 신규 생산라인을 확보한다."))
        pool = select_keyword_storyboard_news([a, b], candidate_pool=True, limit=3)
        self.assertEqual(len(pool), 2)
        out = select_keyword_storyboard_news([a, b], limit=3)
        self.assertEqual(len(out), 1)

    def test_distinct_factory_location_is_not_duplicate(self):
        title = "삼성전자 신규 공장 증설 계획 발표"
        a = self.with_body(self.article("1", title, "삼성전자가 평택 공장 증설 계획을 발표했다."))
        b = self.with_body(self.article("2", title, "삼성전자가 화성 공장 증설 계획을 발표했다."))
        self.assertEqual(len(select_keyword_storyboard_news([a, b], limit=3)), 2)

    def test_distinct_contract_amount_is_not_duplicate(self):
        title = "삼성전자 신규 공급 계약 체결"
        a = self.with_body(self.article("1", title, "삼성전자는 A사와 100억원 공급 계약을 체결했다."))
        b = self.with_body(self.article("2", title, "삼성전자는 A사와 200억원 공급 계약을 체결했다."))
        self.assertEqual(len(select_keyword_storyboard_news([a, b], limit=3)), 2)

    def test_distinct_contract_counterparty_is_not_duplicate(self):
        title = "삼성전자 신규 공급 계약 체결"
        a = self.with_body(self.article("1", title, "삼성전자는 A사와 공급 계약을 체결했다."))
        b = self.with_body(self.article("2", title, "삼성전자는 B사와 공급 계약을 체결했다."))
        self.assertEqual(len(select_keyword_storyboard_news([a, b], limit=3)), 2)

    def test_verified_candidates_replace_unrelated_and_unreadable(self):
        rows = [
            self.article("unrelated", "삼성전자 새로운 계약", "영국 의회는 세금 법안을 처리했다.", score=98),
            self.article("duplicate", "삼성전자 평택 공장 증설", "삼성전자는 평택 공장을 증설했다. 생산 능력이 확대된다.", keyword="증설", score=94),
            self.article("dup2", "삼성전자 평택 공장 증설", "삼성전자는 평택 공장을 증설했다. 투자도 확대한다.", keyword="증설", score=93),
            self.article("unreadable", "삼성전자 신규 수주", "", keyword="신규수주", score=92),
            self.article("new", "삼성전자 화성 공장 증설", "삼성전자는 화성 공장을 증설했다. 연말 양산을 시작한다.", keyword="증설", score=91),
            self.article("deal", "삼성전자 100억원 공급 계약", "삼성전자는 B사와 100억원 공급 계약을 체결했다. 납품을 시작한다.", score=90),
        ]
        bodies = {row["url"]: row["description"] for row in rows}
        bodies[rows[3]["url"]] = ""
        def fetch_details(batch, limit=3, with_sources=False):
            return [
                {"text": bodies[row["url"]],
                 "source": "jsonld_article_body" if bodies[row["url"]] else "fetch_failed"}
                for row in batch
            ]

        article_keywords = {
            "articles": [
                {"keywords": row["article_keywords"], "keyword_details": row["article_keyword_details"],
                 "grounded_tags": [], "stock_entities": ["삼성전자"],
                 "event_owner": "삼성전자", "relation_type": "direct"}
                for row in rows
            ]
        }

        with patch("backend.services.news_result.fetch_stock_news", return_value=rows), \
             patch("backend.services.news_result.score_stock_news", side_effect=lambda items, stock: items), \
             patch("backend.services.news_result.build_connected_keyword_test", return_value=article_keywords), \
             patch("backend.services.news_result.build_simple_today_news", side_effect=lambda items, *a, **k: items), \
             patch("backend.services.news_result.read_selected_article_details", side_effect=fetch_details), \
             patch("backend.services.news_result.build_issue_briefs", side_effect=lambda items, stock, limit, body_texts: [
                 {"summary": body} for body in body_texts
             ]):
            result = build_stock_news_result("삼성전자", market="국내")

        selected = result["storyboard_news_items"]
        keys = [row["url"].split("/")[-1] for row in selected]
        self.assertEqual(len(keys), 3, keys)
        self.assertNotIn("unrelated", keys)
        self.assertNotIn("unreadable", keys)
        self.assertNotIn("dup2", keys)
        self.assertCountEqual(keys, ["duplicate", "new", "deal"])
        self.assertEqual(len(result["paired_news_items"]), len(rows))
        self.assertTrue(all("_central_checked_body" not in item for item in selected))


if __name__ == "__main__":
    unittest.main()
