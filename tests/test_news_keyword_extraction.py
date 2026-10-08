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


    def test_extracts_mixed_korean_amount(self):
        result = build_connected_keyword_test([{
            "title": "삼성전자, 3분기 영업이익 107조4천억원",
            "description": "삼성전자 실적 발표",
            "stocks": [{"name": "삼성전자", "region": "국내"}],
        }], "삼성전자", max_keywords=3)

        article = result["articles"][0]
        self.assertIn("영업이익107조4천억원", article["keywords"])

    def test_normalizes_arrow_growth_direction(self):
        result = build_connected_keyword_test([{
            "title": "삼성전자, 영업이익 782.5%↑",
            "description": "삼성전자 영업이익이 전년 동기 대비 크게 늘었다.",
            "stocks": [{"name": "삼성전자", "region": "국내"}],
        }], "삼성전자", max_keywords=3)

        article = result["articles"][0]
        self.assertIn("영업이익782.5%증가", article["keywords"])

    def test_extracts_consensus_beat_percentage(self):
        result = build_connected_keyword_test([{
            "title": "삼성전자, 3분기 영업익 시장 전망치 1.6% 상회",
            "description": "삼성전자 영업이익이 시장 전망치를 웃돌았다.",
            "stocks": [{"name": "삼성전자", "region": "국내"}],
        }], "삼성전자", max_keywords=3)

        article = result["articles"][0]
        self.assertIn("영업이익전망치1.6%상회", article["keywords"])


    def test_extracts_common_english_nvidia_event_phrases(self):
        result = build_connected_keyword_test([{
            "title": "Nvidia raises guidance on strong AI demand",
            "description": "Nvidia said demand for its AI chips remains strong.",
            "stocks": [{"name": "엔비디아", "region": "미국"}],
        }], "엔비디아", max_keywords=3)

        article = result["articles"][0]
        self.assertEqual(article["status"], "PASS")
        self.assertIn("실적전망상향", article["keywords"])
        self.assertIn("수요증가", article["keywords"])

    def test_extracts_common_english_alphabet_earnings_phrases(self):
        result = build_connected_keyword_test([{
            "title": "Alphabet beats estimates as cloud revenue grows",
            "description": "Alphabet reported stronger cloud sales.",
            "stocks": [{"name": "알파벳", "region": "미국"}],
        }], "알파벳", max_keywords=3)

        article = result["articles"][0]
        self.assertEqual(article["status"], "PASS")
        self.assertIn("예상치상회", article["keywords"])
        self.assertIn("매출증가", article["keywords"])

    def test_extracts_common_english_buyback_and_supply_phrases(self):
        result = build_connected_keyword_test([{
            "title": "Nvidia announces share buyback and new supply agreement",
            "description": "Nvidia signed a supply deal with a partner.",
            "stocks": [{"name": "엔비디아", "region": "미국"}],
        }], "엔비디아", max_keywords=3)

        article = result["articles"][0]
        self.assertIn("자사주매입", article["keywords"])
        self.assertIn("공급계약", article["keywords"])


    def test_preserves_price_subject_in_keyword(self):
        result = build_connected_keyword_test([{
            "title": "삼성전자, HBM 가격 상승에 실적 개선 기대",
            "description": "삼성전자 HBM 수요가 이어지고 있다.",
            "stocks": [{"name": "삼성전자", "region": "국내"}],
        }], "삼성전자", max_keywords=3)

        article = result["articles"][0]
        self.assertIn("HBM가격상승", article["keywords"])
        self.assertNotIn("가격상승", article["keywords"])

    def test_keeps_generic_price_keyword_only_without_named_subject(self):
        result = build_connected_keyword_test([{
            "title": "삼성전자, 가격 상승 영향 점검",
            "description": "삼성전자는 관련 영향을 검토하고 있다.",
            "stocks": [{"name": "삼성전자", "region": "국내"}],
        }], "삼성전자", max_keywords=3)

        article = result["articles"][0]
        self.assertIn("가격상승", article["keywords"])


if __name__ == "__main__":
    unittest.main()
