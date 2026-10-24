"""Offline-only regression tests for experimental full-article reconstruction."""
import unittest

from experiments.full_article_news import compose_news, _sentences


INVESTMENT = (
    "일론 머스크가 자신이 경영하는 테슬라와 스페이스X의 합병을 추진하는 가운데 "
    "새 사업의 가능성을 검토하고 있다. 세계 전기차 시장과 우주 산업의 융합을 둘러싼 "
    "관측이 잇따르고 있다. 아직 사업 투자금과 세부 일정은 확정되지 않은 상태다. "
    "일부 전문가는 새로운 기술 경쟁이 장기간 지속될 것으로 보고 있다. "
    "머스크가 추진하는 인공지능(AI) 데이터센터 사업에 최대 5000억달러를 "
    "투입할 수 있다는 분석이 나왔다. "
    "AI 컴퓨팅 인프라 시장의 주도권이 핵심 배경이라는 설명이다. "
    "다만 실제 자금 지출과 투자 승인은 확인되지 않았다는 점도 덧붙였다."
)
MOBILITY = (
    "모빌리티 및 특수 프로모션 전문기업 퍼플마인이 여러 행사 기획사와 사업 방안을 검토해 왔다. "
    "이 회사는 산업 전반의 광고 수요를 조사하고 차량 운행 환경을 분석했다. "
    "행사장 내 차량 이용 방식도 시험해 왔다. "
    "올해 들어 모빌리티 관련 사업 확대 계획을 구체화했다고 밝혔다. "
    "퍼플마인은 테슬라 사이버트럭을 다수 확보했다. "
    "해당 차량은 렌트 및 광고와 미디어 촬영 지원, VIP 의전 등에 사용될 수 있다. "
    "복수 차량을 이용한 행사도 준비하고 있다. "
    "다만 실제 서비스 개시와 수익 규모는 아직 공개하지 않았다."
)
CLINICAL = (
    "미국 제약사 모더나가 신약 개발 사업을 이어가고 있다. "
    "연구진은 여러 임상 단계에서 안전성과 효과를 검토했다. "
    "이번 발표는 기존 치료제와의 병용 가능성을 살펴본 결과다. "
    "모더나는 암백신 임상 3상 결과를 발표했다. "
    "연구 결과 재발 또는 사망 위험을 42% 낮췄다고 설명했다. "
    "해당 연구는 머크와 공동 개발한 백신에 관한 내용이다. "
    "연구진은 이번 발표에서 연구 평가 지표와 환자 추적 계획도 설명했다. "
    "향후 추가 분석을 통해 장기적인 치료 결과를 확인할 계획이라고 밝혔다. "
    "다만 모든 환자에게 동일한 효능이 나타난다는 뜻은 아니다."
)


class FullArticleNewsExperimentTest(unittest.TestCase):
    def test_last_half_changes_headline(self):
        first_three = " ".join(_sentences(INVESTMENT)[:3])
        self.assertNotIn("5000억달러", first_three)
        result = compose_news(INVESTMENT, "https://example.org/investment")
        self.assertEqual(result["status"], "experimental", result)
        self.assertIn("5000억달러", result["headline"])
        self.assertIn("가능성", result["headline"])
        self.assertNotIn("확정", result["headline"])
        self.assertGreaterEqual(len(result["body"].split(".")), 3)
        self.assertEqual(result["source_url"], "https://example.org/investment")

    def test_uses_actual_business_actor_not_car_maker(self):
        result = compose_news(MOBILITY, "https://example.org/mobility")
        self.assertEqual(result["status"], "experimental", result)
        self.assertTrue(result["headline"].startswith("퍼플마인"), result)
        self.assertNotIn("테슬라, ", result["headline"])
        self.assertIn("광고", result["body"])
        self.assertIn("사업확대", result["tags"])

    def test_clinical_number_only_if_body_supports_it(self):
        result = compose_news(CLINICAL, "https://example.org/clinical")
        self.assertEqual(result["status"], "experimental", result)
        self.assertIn("42%", result["headline"])
        self.assertIn("모더나", result["headline"])
        self.assertIn("임상시험", result["tags"])

    def test_does_not_copy_publisher_title(self):
        original = "완전히 다른 출판사 제목…누가 썼나"
        result = compose_news(INVESTMENT, "https://example.org/1")
        self.assertNotIn(original, result["headline"])
        for paragraph in result["body"].split("\n\n"):
            self.assertNotIn(paragraph, INVESTMENT)

    def test_ambiguous_body_fails_closed(self):
        unclear = " ".join([
            "기업 관계자들이 새로운 사업 방향에 관해 논의했다.",
            "아직 투자 방식이나 비용을 확정하지 않았다고 전했다.",
            "시장 참여자들은 이번 논의가 향후 사업에 영향을 줄 것으로 예상했다.",
            "현재까지 구체적인 계약이나 발표 내용은 확인되지 않았다.",
            "일각에서는 시장 상황에 따라 계획이 변동될 가능성이 있다고 봤다.",
            "회사 측은 사업을 확정하기 전에 추가 논의가 필요하다고 설명했다.",
        ])
        result = compose_news(unclear, "https://example.org/2")
        self.assertEqual(result["status"], "not_supported", result)
        self.assertFalse(result["headline"])
        self.assertFalse(result["body"])

    def test_no_two_sentence_cap(self):
        result = compose_news(INVESTMENT, "https://example.org/3")
        self.assertEqual(result["status"], "experimental", result)
        self.assertGreaterEqual(len(result["body"].split("\n\n")), 3)


if __name__ == "__main__":
    unittest.main()
