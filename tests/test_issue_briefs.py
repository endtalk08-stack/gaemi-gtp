import unittest

from backend.services.issue_briefs import build_issue_briefs


class IssueBriefTests(unittest.TestCase):
    def test_ai_memory_brief_never_returns_source_title_or_description(self):
        source_title = "원문 제목은 화면에 나오면 안 됩니다"
        source_description = "원문 문장도 화면에 나오면 안 됩니다"
        result = build_issue_briefs([{
            "title": source_title,
            "description": source_description,
            "storyboard_time": "11:40",
            "storyboard_keywords": ["AI메모리"],
            "movement_signals": [{"label": "메모리가격", "tone": "positive"}],
            "stock_entities": ["삼성전자", "SK하이닉스"],
            "themes": ["반도체", "AI·소프트웨어"],
            "issues": ["반도체 업황", "AI 투자"],
        }], "삼성전자")

        self.assertEqual(len(result), 1)
        brief = result[0]
        self.assertEqual(brief["time"], "11:40")
        self.assertEqual(brief["headline"], "AI 메모리 이슈")
        self.assertIn("AI 메모리", brief["summary"])
        self.assertIn("메모리 가격", brief["summary"])
        self.assertEqual(len(brief["summary"].splitlines()), 2)
        self.assertEqual(brief["stock_names"], ["삼성전자", "SK하이닉스"])
        self.assertIn("AI메모리", brief["tags"])
        self.assertNotIn(source_title, str(brief))
        self.assertNotIn(source_description, str(brief))

    def test_unknown_signal_uses_structured_theme_without_source_copy(self):
        result = build_issue_briefs([{
            "title": "복사하면 안 되는 원문",
            "description": "복사하면 안 되는 설명",
            "storyboard_time": "10:44",
            "storyboard_keywords": ["새로운신호"],
            "stock_entities": ["삼성전자"],
            "themes": ["반도체"],
            "issues": [],
        }], "삼성전자")

        self.assertEqual(result, [])  # A single unknown label is not enough for a grounded explanation.

    def test_central_brief_uses_materials_instead_of_generic_attention_copy(self):
        result = build_issue_briefs([{
            "storyboard_time": "15:38",
            "storyboard_keywords": ["수익성개선"],
            "movement_signals": [
                {"label": "HBM", "tone": "positive"},
                {"label": "공급부족", "tone": "positive"},
            ],
            "stock_entities": ["삼성전자"],
            "themes": ["반도체"],
        }], "삼성전자")

        self.assertEqual(result[0]["headline"], "수익성 개선·HBM 이슈")
        self.assertIn("수익성 개선·HBM", result[0]["summary"])
        self.assertIn("공급 부족", result[0]["summary"])
        self.assertEqual(len(result[0]["summary"].splitlines()), 2)
        self.assertNotIn("주목", str(result[0]))
        self.assertNotIn("관심이 모이고", str(result[0]))

    def test_central_brief_formats_memory_price_issue(self):
        result = build_issue_briefs([{
            "storyboard_time": "15:24",
            "storyboard_keywords": ["가격상승"],
            "movement_signals": [
                {"label": "메모리가격", "tone": "positive"},
                {"label": "반도체호황", "tone": "positive"},
            ],
            "stock_entities": ["삼성전자"],
            "themes": ["반도체"],
        }], "삼성전자")

        self.assertEqual(result[0]["headline"], "메모리 가격 상승 이슈")
        self.assertIn("메모리 가격 상승", result[0]["summary"])
        self.assertIn("반도체 업황", result[0]["summary"])
        self.assertEqual(len(result[0]["summary"].splitlines()), 2)

    def test_central_brief_uses_additional_article_facts_without_repeating_headline(self):
        result = build_issue_briefs([{
            "storyboard_time": "15:58",
            "storyboard_keywords": ["공급확대"],
            "article_keywords": ["공급확대", "해외진출", "생산확대"],
            "stock_entities": ["현대차", "기아"],
            "themes": ["자동차·모빌리티"],
        }], "현대차")

        self.assertEqual(result[0]["headline"], "공급 확대 이슈")
        self.assertIn("공급 확대", result[0]["summary"])
        self.assertIn("해외 진출", result[0]["summary"])
        self.assertIn("생산 확대", result[0]["summary"])
        self.assertEqual(len(result[0]["summary"].splitlines()), 3)
        self.assertEqual(result[0]["tags"], ["공급확대", "해외진출", "생산확대"])
        self.assertEqual(result[0]["stock_names"], ["현대차", "기아"])
    def test_central_brief_turns_compact_facts_into_readable_copy(self):
        result = build_issue_briefs([{
            "storyboard_time": "17:31",
            "storyboard_keywords": ["영업이익100조원기대"],
            "article_keywords": ["영업이익100조원기대", "자사주매입", "실적발표"],
            "stock_entities": ["삼성전자"],
            "themes": ["반도체"],
        }], "삼성전자")

        self.assertEqual(result[0]["headline"], "영업이익 이슈")
        self.assertIn("영업이익 100조원 기대", result[0]["summary"])
        self.assertIn("기대", result[0]["summary"])
        self.assertIn("자사주 매입", result[0]["summary"])
        self.assertEqual(len(result[0]["summary"].splitlines()), 2)
        self.assertEqual(
            result[0]["tags"],
            ["영업이익", "자사주매입", "실적발표"],
        )
        self.assertNotIn("기사", result[0]["summary"])

    def test_central_brief_adds_issue_suffix_for_buyback_event(self):
        result = build_issue_briefs([{
            "storyboard_time": "17:31",
            "storyboard_keywords": ["자사주소각"],
            "article_keywords": ["자사주소각", "영업이익100조원기대"],
            "stock_entities": ["삼성전자"],
            "themes": ["반도체"],
        }], "삼성전자")

        self.assertEqual(result[0]["headline"], "자사주 소각 이슈")
        self.assertIn("자사주 소각", result[0]["summary"])
        self.assertIn("영업이익 100조원 기대", result[0]["summary"])
        self.assertEqual(len(result[0]["summary"].splitlines()), 2)
        self.assertNotIn("언급", result[0]["summary"])

    def test_central_brief_cycles_three_summary_endings_without_stock_subject(self):
        result = build_issue_briefs([
            {
                "storyboard_time": "17:31",
                "storyboard_keywords": ["자사주소각"],
                "article_keywords": ["자사주소각", "영업이익100조원기대"],
                "stock_entities": ["삼성전자"],
            },
            {
                "storyboard_time": "17:20",
                "storyboard_keywords": ["공급확대"],
                "article_keywords": ["공급확대", "해외진출"],
                "stock_entities": ["현대차", "기아"],
            },
            {
                "storyboard_time": "17:10",
                "storyboard_keywords": ["AI메모리"],
                "article_keywords": ["AI메모리", "HBM수요"],
                "stock_entities": ["삼성전자", "SK하이닉스"],
            },
        ], "삼성전자")

        self.assertEqual(len(result), 3)
        self.assertTrue(all(len(brief["summary"].splitlines()) == 2 for brief in result))
        self.assertIn("자사주 소각", result[0]["summary"])
        self.assertIn("해외 진출", result[1]["summary"])
        self.assertIn("HBM 수요", result[2]["summary"])
        self.assertNotIn("삼성전자에서는", " ".join(brief["summary"] for brief in result))
        self.assertNotIn("현대차에서는", " ".join(brief["summary"] for brief in result))

    def test_central_numeric_title_and_tags_hide_extraction_pattern(self):
        result = build_issue_briefs([{
            "storyboard_time": "19:54",
            "published_at": "2026-10-09T10:54:00+00:00",
            "storyboard_keywords": ["영업이익107조4000억원"],
            "article_keywords": [
                "영업이익107조4000억원",
                "영업이익107.4조원",
                "영업이익2.42%감소",
            ],
            "stock_entities": ["삼성전자", "SK하이닉스", "엔비디아"],
        }], "삼성전자")

        self.assertEqual(result[0]["headline"], "영업이익 이슈")
        self.assertEqual(result[0]["tags"], ["영업이익"])
        self.assertIn("107조4000억원", result[0]["summary"])
        self.assertNotIn("107조4000억원", result[0]["headline"])
        self.assertNotIn("107조4000억원", " ".join(result[0]["tags"]))


    def test_central_brief_displays_specific_price_subject(self):
        result = build_issue_briefs([{
            "storyboard_time": "00:12",
            "storyboard_keywords": ["HBM가격상승"],
            "article_keywords": ["HBM가격상승", "실적개선"],
            "stock_entities": ["삼성전자"],
        }], "삼성전자")

        self.assertEqual(result[0]["headline"], "HBM 가격 상승 이슈")
        self.assertIn("HBM 가격 상승", result[0]["summary"])


    def test_central_product_event_uses_grounded_product_name(self):
        result = build_issue_briefs([{
            "storyboard_time": "21:00",
            "storyboard_keywords": ["제품공개"],
            "article_keywords": ["제품공개", "우주경쟁"],
            "grounded_tags": ["Gemini", "미국"],
            "stock_entities": ["알파벳"],
        }], "알파벳")

        self.assertEqual(result[0]["headline"], "Gemini 제품 공개 이슈")
        self.assertIn("Gemini 제품 공개", result[0]["summary"])
        self.assertEqual(result[0]["tags"][0], "Gemini")


    def test_currency_and_earnings_are_described_as_separate_facts(self):
        result = build_issue_briefs([{
            "storyboard_time": "06:03",
            "storyboard_keywords": ["원화강세"],
            "article_keywords": ["원화강세", "역대급실적"],
            "stock_entities": ["삼성전자"],
        }], "삼성전자")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["headline"], "원화 강세 이슈")
        self.assertEqual(len(result[0]["summary"].splitlines()), 2)
        self.assertIn("원화 강세", result[0]["summary"])
        self.assertIn("역대급 실적", result[0]["summary"])
        self.assertNotIn("때문에", result[0]["summary"])

    def test_unrelated_profit_figures_and_buyback_are_not_merged(self):
        result = build_issue_briefs([{
            "storyboard_time": "05:42",
            "storyboard_keywords": ["영업이익782.5%증가"],
            "article_keywords": ["영업이익782.5%증가", "영업이익107조원", "자사주소각"],
            "stock_entities": ["삼성전자"],
        }], "삼성전자")

        self.assertEqual(len(result), 1)
        summary = result[0]["summary"]
        self.assertEqual(len(summary.splitlines()), 3)
        self.assertIn("영업이익 782.5% 증가", summary)
        self.assertIn("영업이익 107조원", summary)
        self.assertIn("자사주 소각", summary)
        self.assertNotIn("따라서", summary)

    def test_central_brief_speaks_as_issue_not_article_report(self):
        result = build_issue_briefs([{
            "storyboard_time": "06:50",
            "storyboard_keywords": ["영업이익107조원"],
            "article_keywords": ["영업이익107조원", "외국인매도", "잠정실적발표"],
            "stock_entities": ["삼성전자"],
        }], "삼성전자")

        self.assertEqual(len(result), 1)
        summary = result[0]["summary"]
        self.assertIn("영업이익 107조원", summary)
        self.assertIn("외국인 매도", summary)
        self.assertNotIn("기사", summary)
        self.assertNotIn("언급", summary)
        self.assertNotIn("관련 내용을", summary)

    def test_contract_detail_omits_unlabeled_percentages(self):
        result = build_issue_briefs([{
            "storyboard_time": "06:24",
            "storyboard_keywords": ["계약체결"],
            "article_keywords": ["계약체결", "공급계약", "단일판매"],
            "stock_entities": ["삼성전자"],
            "detail_facts": {
                "counterparty": "",
                "amount": "",
                "region": [],
                "key_numbers": ["5.49%", "25%"],
            },
        }], "삼성전자")

        self.assertEqual(len(result), 1)
        self.assertNotIn("5.49%", result[0]["summary"])
        self.assertNotIn("25%", result[0]["summary"])
        self.assertNotIn("기사", result[0]["summary"])
        self.assertNotIn("언급", result[0]["summary"])

    def test_central_contract_brief_uses_structured_counterparty_and_amount(self):
        result = build_issue_briefs([{
            "storyboard_time": "20:32",
            "storyboard_keywords": ["공급계약"],
            "article_keywords": ["공급계약"],
            "stock_entities": ["알파벳"],
            "detail_facts": {
                "product_name": "",
                "counterparty": "Constellation Energy",
                "amount": "$3.6 billion",
                "region": ["미국"],
                "announcer": "알파벳",
                "key_numbers": ["20-year", "3.59 GW", "890 MW"],
            },
        }], "알파벳")

        self.assertEqual(result[0]["headline"], "공급 계약 이슈")
        self.assertIn("Constellation Energy", result[0]["summary"])
        self.assertIn("$3.6 billion", result[0]["summary"])
        self.assertNotIn("20-year", result[0]["summary"])
        self.assertEqual(len(result[0]["summary"].splitlines()), 2)
        self.assertNotIn("기사", result[0]["summary"])
        self.assertNotIn("언급", result[0]["summary"])


if __name__ == "__main__":
    unittest.main()
