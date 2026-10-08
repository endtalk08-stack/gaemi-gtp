import unittest

from backend.services.issue_briefs import build_issue_briefs, build_news_test_articles


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
        self.assertEqual(brief["headline"], "AI 메모리·메모리 가격 이슈")
        self.assertEqual(
            brief["summary"],
            "AI 메모리, 메모리 가격 관련 내용이\n기사에서 함께 언급됐어요.",
        )
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

        self.assertEqual(result[0]["headline"], "새로운신호 관련 이슈")
        self.assertEqual(
            result[0]["summary"],
            "새로운신호 관련 내용이\n기사에서 언급됐어요.",
        )
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

        self.assertEqual(result[0]["headline"], "수익성 개선·HBM 공급 이슈")
        self.assertEqual(
            result[0]["summary"],
            "수익성 개선 흐름과 HBM, 공급 부족 관련 내용이\n기사에서 함께 언급됐어요.",
        )
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

        self.assertEqual(result[0]["headline"], "메모리 가격 상승 기대")
        self.assertEqual(
            result[0]["summary"],
            "메모리 가격 상승과 반도체 업황 관련 기대가\n기사에서 함께 언급됐어요.",
        )

    def test_news_test_articles_keep_only_display_fields(self):
        result = build_news_test_articles([{
            "title": "원문 제목",
            "description": "원문 설명",
            "storyboard_time": "11:40",
            "storyboard_keywords": ["AI메모리"],
            "movement_signals": [{"label": "메모리가격", "tone": "positive"}],
            "stock_entities": ["삼성전자", "SK하이닉스"],
            "themes": ["반도체"],
        }], "삼성전자")

        self.assertEqual(set(result[0]), {"id", "time", "headline", "body", "tags", "stock_names"})
        self.assertEqual(result[0]["headline"], "AI 메모리 기대감에 반도체주 강세")
        self.assertEqual(
            result[0]["body"],
            "AI 서버 투자와 메모리 가격 상승 기대가 이어지며\n"
            "삼성전자와 SK하이닉스에 매수세가 유입되고 있어요.\n\n"
            "삼성전자는 실적 개선 기대가, SK하이닉스는 HBM 수요가\n"
            "각각 주가 흐름의 핵심 재료로 언급됐어요.",
        )
        self.assertEqual(result[0]["tags"], ["특징주", "AI메모리", "반도체"])
        self.assertNotIn("원문 제목", str(result[0]))
        self.assertNotIn("원문 설명", str(result[0]))


if __name__ == "__main__":
    unittest.main()
