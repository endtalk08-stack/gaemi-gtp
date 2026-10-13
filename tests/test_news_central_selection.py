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

    def test_hyundai_three_reports_same_india_investment_are_one_story(self):
        # Realistic publisher variants: different labels, titles, Korean money spacing.
        rows = [
            self.article(
                "pressnine", "현대차그룹 정의선 회장 인도 모디 총리 면담",
                "정의선 현대자동차그룹 회장이 13일 인도 뉴델리에서 나렌드라 모디 총리와 면담했다. "
                "현대차그룹은 향후 7년간 약 155억 달러를 인도에 투자할 계획이다. "
                "신공장과 연구개발 인프라를 확충한다.",
                keyword="인도사업", score=100,
            ),
            self.article(
                "another", "현대차 현지 사업 장기 성장 전략 발표",
                "정의선 현대차그룹 회장이 나렌드라 모디 인도 총리와 만났다. "
                "2032년까지 인도에 155억달러를 투자해 생산능력을 확충한다. "
                "현지 공급망과 미래 모빌리티 사업도 강화한다.",
                keyword="투자확대", score=99,
            ),
            self.article(
                "third", "정의선 모디 총리 만남 7년간 대규모 투자",
                "정의선 현대차그룹 회장이 인도에 연 140만대 생산체제를 구축하겠다고 설명했다. "
                "나렌드라 모디 총리와 만나 올해부터 7년간 약 155억달러(약 20조8000억원) "
                "규모의 투자를 계획한다고 밝혔다. 자동차 사업을 강화한다.",
                keyword="생산체제", score=98,
            ),
        ]
        verified = []
        for row in rows:
            article = self.with_body(row)
            article["event_owner"] = "현대차"
            verified.append(article)

        self.assertEqual(
            len(select_keyword_storyboard_news(verified, candidate_pool=True, limit=3)), 3
        )
        result = select_keyword_storyboard_news(verified, limit=3)
        self.assertEqual(len(result), 1, result)
        self.assertEqual(result[0]["event_owner"], "현대차")

    def test_investments_with_different_budgets_or_countries_stay_distinct(self):
        lead = "현대차가 인도에 155억 달러를 투자하기로 했다. 현지 설비를 늘린다."
        other_budget = "현대차가 인도에 200억 달러를 투자하기로 했다. 현지 설비를 늘린다."
        other_country = "현대차가 베트남에 155억 달러를 투자하기로 했다. 현지 설비를 늘린다."
        # Deliberately identical headlines: the verified facts must win.
        rows = [
            self.with_body(self.article("i", "현대차 해외 투자 발표", lead, keyword="투자")),
            self.with_body(self.article("b", "현대차 해외 투자 발표", other_budget, keyword="투자")),
            self.with_body(self.article("c", "현대차 해외 투자 발표", other_country, keyword="투자")),
        ]
        for row in rows:
            row["event_owner"] = "현대차"
        self.assertEqual(len(select_keyword_storyboard_news(rows, limit=3)), 3)

    def test_verified_candidates_replace_unrelated_and_unreadable(self):
        rows = [
            self.article("unrelated", "삼성전자 새로운 계약", "영국 의회는 세금 법안을 처리했다.", score=98),
            self.article("duplicate", "삼성전자 평택 공장 증설", "삼성전자는 평택 공장을 증설했다. 생산 능력이 확대된다.", keyword="증설", score=94),
            self.article("dup2", "삼성전자 평택 공장 증설", "삼성전자는 평택 공장을 증설했다. 투자도 확대한다.", keyword="증설", score=93),
            self.article("unreadable", "삼성전자 신규 수주", "", keyword="신규수주", score=92),
            self.article("new", "삼성전자 화성 공장 증설", "삼성전자는 화성 공장을 증설했다. 연말 양산을 시작한다.", keyword="증설", score=91),
            self.article("deal", "삼성전자 100억원 공급 계약", "삼성전자는 B사와 100억원 공급 계약을 체결했다. 납품을 시작한다.", score=90),
        ]
        duplicate_pair = [self.with_body(rows[1]), self.with_body(rows[2])]
        self.assertEqual(
            len(select_keyword_storyboard_news(duplicate_pair, limit=3)),
            1,
            "Two same-factory same-title articles must be merged",
        )
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
