import unittest

from backend.services.issue_briefs import build_issue_briefs, market_material_title_and_tags


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
        self.assertEqual(brief["summary"], "AI 메모리와 메모리 가격 관련 이슈가 있어.")
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

        self.assertEqual(result[0]["headline"], "새로운신호")
        self.assertEqual(result[0]["summary"], "")
        self.assertNotIn("복사하면 안 되는", str(result[0]))

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
        self.assertEqual(result[0]["summary"], "수익성 개선·HBM과 공급 부족 관련 이슈가 있어.")
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
        self.assertEqual(result[0]["summary"], "메모리 가격 상승과 반도체 업황 관련 이슈가 있어.")

    def test_central_brief_uses_additional_article_facts_without_repeating_headline(self):
        result = build_issue_briefs([{
            "storyboard_time": "15:58",
            "storyboard_keywords": ["공급확대"],
            "article_keywords": ["공급확대", "해외진출", "생산확대"],
            "stock_entities": ["현대차", "기아"],
            "themes": ["자동차·모빌리티"],
        }], "현대차")

        self.assertEqual(result[0]["headline"], "공급 확대 이슈")
        self.assertEqual(result[0]["summary"], "공급 확대, 해외 진출, 생산 확대 관련 이슈가 있어.")
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
        self.assertEqual(result[0]["summary"], "영업이익 100조원 기대가 나오고, 자사주 매입 관련 이슈가 있어.")
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
        self.assertEqual(
            result[0]["summary"],
            "자사주 소각과 영업이익 100조원 기대 관련 이슈가 있어.",
        )
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

        self.assertEqual(
            [brief["summary"] for brief in result],
            [
                "자사주 소각과 영업이익 100조원 기대 관련 이슈가 있어.",
                "공급 확대와 해외 진출 관련 내용을 확인했어.",
                "AI 메모리와 HBM 수요 관련 이슈도 있었어.",
            ],
        )
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
        self.assertEqual(
            result[0]["summary"],
            "Constellation Energy와 계약, 규모 $3.6 billion, 20-year 관련 내용을 확인했어.",
        )



    def test_market_material_headline_one_topic_but_all_tags_preserved(self):
        for stock in ("SK하이닉스", "테슬라"):
            text = f"{stock}, CPI 예상 상회로 금리 인상 우려. 트럼프 발언에 시장 긴장"
            headline, tags = market_material_title_and_tags(text)
            self.assertEqual(headline, "CPI 예상 상회 이슈")
            self.assertEqual(tags, ["CPI예상상회", "금리인상우려", "트럼프발언"])
            self.assertNotIn(" · ", headline)

        headline, tags = market_material_title_and_tags(
            "SK하이닉스, CPI 예상 상회로 금리 인상 우려. 트럼프 발언에 시장 긴장",
            limit=2,
        )
        self.assertEqual(headline, "CPI 예상 상회 이슈")
        self.assertEqual(tags, ["CPI예상상회", "금리인상우려"])

    def test_market_material_matching_does_not_cross_sentences(self):
        title, tags = market_material_title_and_tags(
            "SK하이닉스 CPI 발표 예정. 예상치 상회 논란과 금리 인상 우려"
        )
        self.assertEqual(title, "금리 인상 우려 이슈")
        self.assertEqual(tags, ["금리인상우려"])

    def test_market_materials_are_separate_from_original_company_body_titles(self):
        from backend.services.issue_briefs import _body_title_and_tags
        self.assertEqual(
            _body_title_and_tags("CPI 예상 상회와 금리 인상 우려가 확대됐다."),
            ("기사 주요 내용", []),
        )
        self.assertEqual(
            _body_title_and_tags("삼성전자가 반도체 공급 계약을 체결했다."),
            ("공급 계약 이슈", ["공급계약"]),
        )

    def test_market_materials_are_fact_grounded_not_price_guesses(self):
        cases = [
            ("SK하이닉스, CPI 예상 상회로 금리 인상 우려", ["CPI예상상회", "금리인상우려"]),
            ("SK하이닉스, 미국 CPI 3.7% 상승 예상치 웃돌아", ["CPI예상상회"]),
            ("트럼프 대통령 관세 강화 발언에 반도체주 경계", ["트럼프관세"]),
            ("트럼프 발언으로 미국 정책 불확실성 확대", ["트럼프발언"]),
            ("FOMC 연준 금리 동결 발표", ["FOMC금리동결"]),
            ("예상보다 높은 CPI, 금리 인상 확률 확대", ["CPI예상상회", "금리인상가능성"]),
            ("원달러 환율 급등, 달러 강세", ["환율급등", "달러강세"]),
            ("삼성전자 공급 계약 체결로 주가 상승", []),
            ("SK하이닉스 주가 3% 하락", []),
        ]
        for article, expected_tags in cases:
            with self.subTest(article=article):
                heading, tags = market_material_title_and_tags(article)
                self.assertEqual(tags, expected_tags)
                self.assertEqual(bool(heading), bool(expected_tags))

if __name__ == "__main__":
    unittest.main()
