import unittest
from backend.services.business_material_events import business_material_title_and_tags as detect


class BusinessMaterialTests(unittest.TestCase):
    def test_positive_negative(self):
        examples = [
            ("SK하이닉스 실적 전망 상향 발표","실적전망상향","positive"),
            ("SK하이닉스 가이던스 하향 발표","실적전망하향","negative"),
            ("SK하이닉스 고객사 발주 확대 발표","고객사발주확대","positive"),
            ("SK하이닉스 고객사 발주 축소 발표","고객사발주축소","negative"),
            ("HD현대 수주잔고 증가","수주잔고증가","positive"),
            ("HD현대 수주잔고 감소","수주잔고감소","negative"),
            ("반도체 산업 공급 과잉 심화","공급과잉","negative"),
            ("반도체 산업 공급 부족 심화","공급부족","positive"),
            ("배터리 재고 급증","재고증가","negative"),
            ("배터리 재고 감소","재고감소","positive"),
            ("삼성전자 공장 가동 중단","생산중단","negative"),
            ("삼성전자 공장 가동 재개","생산재개","positive"),
            ("제약사 임상 3상 성공 발표","임상시험성공","positive"),
            ("제약사 임상 3상 실패 발표","임상시험실패","negative"),
            ("제약사 신약 승인 획득","신약승인","positive"),
            ("제약사 신약 승인 거절","신약승인거절","negative"),
        ]
        for article, label, tone in examples:
            with self.subTest(article=article):
                heading, tags, direction = detect(article)
                self.assertEqual(tags, [label])
                self.assertEqual(direction, tone)
                self.assertTrue(heading.endswith(" 이슈"))

    def test_false_positive(self):
        for article in (
            "SK하이닉스 주가 하락", "SK하이닉스 공급 과잉 우려",
            "SK하이닉스 임상 성공 가능성", "고객사 발주 축소 부인",
            "공장 가동 중단 루머", "삼성전자 실적 전망 하향 검토",
            "수주잔고 감소 예상",
        ):
            with self.subTest(article=article):
                self.assertEqual(detect(article), ("", [], ""))

    def test_title_single_all_evidenced_tags(self):
        heading, tags, tone = detect("반도체 산업 공급 부족. SK하이닉스 고객사 발주 확대")
        self.assertEqual(heading, "공급 부족 이슈")
        self.assertEqual(tags, ["공급부족", "고객사발주확대"])
        self.assertEqual(tone, "positive")

    def test_no_cross_sentence_synthetic_reasons(self):
        self.assertEqual(detect("SK하이닉스 공급. 과잉 우려"), ("", [], ""))
