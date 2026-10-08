import unittest

from backend.analysis.news.scoring import build_connected_keyword_test


class ConnectedKeywordExtractionTests(unittest.TestCase):
    def test_extracts_multiple_grounded_facts_from_one_article(self):
        result = build_connected_keyword_test([{
            "title": "현대차, 해외 진출 확대하며 공급 확대",
            "description": "현대차는 현지 수요에 맞춰 생산 확대 계획도 밝혔다.",
            "stocks": [
                {"name": "현대차", "region": "국내"},
                {"name": "기아", "region": "국내"},
            ],
        }], "현대차", max_keywords=3)

        article = result["articles"][0]
        self.assertEqual(article["keywords"], ["공급확대", "해외진출", "생산확대"])
        self.assertEqual([item["source"] for item in article["keyword_details"]], [
            "title-rule",
            "title-rule",
            "description-rule",
        ])


    def test_extracts_numeric_financial_facts_without_inventing_context(self):
        result = build_connected_keyword_test([{
            "title": "삼성전자, 3분기 영업이익 107조4,000억원... 역대 최대 실적",
            "description": "삼성전자 영업이익은 전년 동기 대비 782.5% 증가했다.",
            "stocks": [{"name": "삼성전자", "region": "국내"}],
        }], "삼성전자", max_keywords=3)

        article = result["articles"][0]
        self.assertEqual(article["keywords"], [
            "영업이익107조4,000억원",
            "사상최대실적",
            "영업이익782.5%증가",
        ])
        self.assertEqual(article["keyword_details"][0]["source"], "title-fact")
        self.assertEqual(article["keyword_details"][2]["source"], "description-fact")

    def test_preserves_uncertainty_for_expansion_review(self):
        result = build_connected_keyword_test([{
            "title": "삼성전자, 내년 생산능력 2배 확대 검토",
            "description": "삼성전자는 HBM 수요에 대응하는 방안을 검토 중이다.",
            "stocks": [{"name": "삼성전자", "region": "국내"}],
        }], "삼성전자", max_keywords=3)

        article = result["articles"][0]
        self.assertEqual(article["keywords"][0], "생산능력2배확대검토")
        self.assertNotIn("생산능력2배확대", article["keywords"])

    def test_description_numeric_fact_requires_selected_stock_nearby(self):
        result = build_connected_keyword_test([{
            "title": "삼성전자와 SK하이닉스 실적 전망",
            "description": "SK하이닉스 영업이익은 50조원으로 예상됐다. 삼성전자는 별도 수치를 제시하지 않았다.",
            "stocks": [
                {"name": "삼성전자", "region": "국내"},
                {"name": "SK하이닉스", "region": "국내"},
            ],
        }], "삼성전자", max_keywords=3)

        article = result["articles"][0]
        self.assertNotIn("영업이익50조원예상", article["keywords"])


    def test_accepts_common_operating_profit_abbreviation_and_margin(self):
        result = build_connected_keyword_test([{
            "title": "삼성전자 3Q 영업익 107.4조·매출 195조",
            "description": "삼성전자 영업이익률은 55.1%를 기록했다.",
            "stocks": [{"name": "삼성전자", "region": "국내"}],
        }], "삼성전자", max_keywords=3)

        article = result["articles"][0]
        self.assertIn("영업이익107.4조", article["keywords"])
        self.assertIn("매출195조", article["keywords"])
        self.assertIn("영업이익률55.1%", article["keywords"])

    def test_uncertainty_does_not_leak_across_next_clause(self):
        result = build_connected_keyword_test([{
            "title": "삼성전자 영업이익 107조원 기록…4분기 117조원 전망",
            "description": "삼성전자는 3분기 실적을 발표했다.",
            "stocks": [{"name": "삼성전자", "region": "국내"}],
        }], "삼성전자", max_keywords=3)

        article = result["articles"][0]
        self.assertIn("영업이익107조원", article["keywords"])
        self.assertNotIn("영업이익107조원전망", article["keywords"])


if __name__ == "__main__":
    unittest.main()
