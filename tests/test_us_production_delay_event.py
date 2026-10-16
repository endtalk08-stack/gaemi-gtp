"""Do not lose a confirmed postponement or invent an issue from rumors."""
import unittest
from backend.services.business_material_events import business_material_title_and_tags


class ProductionDelayTests(unittest.TestCase):
    def test_tesla_roadster_report_has_a_supported_event(self):
        snippet = (
            "미국 전기차 업체 테슬라가 차세대 스포츠카 로드스터의 "
            "양산 시점을 2028년으로 또다시 미뤘다."
        )
        headline, labels, direction = business_material_title_and_tags(snippet)
        self.assertEqual(headline, "양산·출시 일정 연기 이슈")
        self.assertEqual(labels, ["제품일정연기"])
        self.assertEqual(direction, "negative")

    def test_explicit_launch_postponements(self):
        for sentence in (
            "회사 측은 신제품 출시 일정을 내년으로 연기했다.",
            "테슬라는 로드스터 양산 계획을 2028년으로 늦췄다.",
            "기업은 제품 출시 시점을 다시 미뤘다고 밝혔다.",
        ):
            with self.subTest(sentence=sentence):
                _, labels, direction = business_material_title_and_tags(sentence)
                self.assertIn("제품일정연기", labels)
                self.assertEqual(direction, "negative")

    def test_rumors_and_price_only_are_not_catalysts(self):
        for sentence in (
            "테슬라가 양산 일정을 미룰 가능성이 제기됐다.",
            "테슬라의 출시 일정 연기 우려로 주가가 내렸다.",
            "로드스터 양산 일정은 2028년이 될 것으로 예상된다.",
            "테슬라 주가가 전날보다 3% 하락했다.",
            "테슬라의 양산 시점을 앞당겼다.",
            "테슬라가 로드스터를 출시할 예정이다.",
        ):
            with self.subTest(sentence=sentence):
                self.assertEqual(business_material_title_and_tags(sentence), ("", [], ""))

    def test_other_existing_rules_unchanged(self):
        self.assertEqual(
            business_material_title_and_tags("삼성전자 공장 가동 중단")[1],
            ["생산중단"]
        )
        self.assertEqual(
            business_material_title_and_tags("반도체 산업 공급 부족 심화")[1],
            ["공급부족"]
        )


if __name__ == "__main__":
    unittest.main()
