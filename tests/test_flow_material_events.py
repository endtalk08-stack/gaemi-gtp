import unittest
from backend.services.flow_material_events import flow_material_title_and_tags as detect


class FlowTests(unittest.TestCase):
    def test_upside_downside_flow(self):
        cases = [
            ("삼성전자 기관 순매수", "기관순매수", "positive"),
            ("삼성전자 기관 순매도", "기관순매도", "negative"),
            ("하이닉스 연기금 순매수", "연기금순매수", "positive"),
            ("하이닉스 연기금 순매도", "연기금순매도", "negative"),
            ("삼성전자 프로그램 순매수", "프로그램순매수", "positive"),
            ("삼성전자 프로그램 순매도", "프로그램순매도", "negative"),
            ("삼성전자 대주주 지분 매수", "대주주지분매수", "positive"),
            ("삼성전자 대주주 지분 매각", "대주주지분매각", "negative"),
            ("삼성전자 블록딜 매각", "블록딜매각", "neutral"),
            ("삼성전자 보호예수 해제", "보호예수해제", "neutral"),
            ("삼성전자 보호예수 연장", "보호예수연장", "neutral"),
            ("삼성전자 MSCI 지수 신규 편입", "지수편입", "positive"),
            ("삼성전자 MSCI 지수 편출", "지수편출", "negative"),
            ("삼성전자 공매도 급증", "공매도급증", "negative"),
            ("삼성전자 공매도 급감", "공매도급감", "positive"),
            ("삼성전자 반대매매 발생", "반대매매발생", "negative"),
        ]
        for article, expected, direction in cases:
            with self.subTest(article=article):
                headline, tags, tone = detect(article)
                self.assertEqual(tags, [expected])
                self.assertEqual(tone, direction)
                self.assertTrue(headline.endswith(" 이슈"))

    def test_no_guess(self):
        for article in (
            "기관 매도 예정", "삼성전자 주가 하락", "삼성전자 블록딜 매각 가능성",
            "MSCI 지수 편출 우려", "삼성전자 기관 순매도 부인",
            "보호예수 해제 예정",
        ):
            with self.subTest(article=article):
                self.assertEqual(detect(article), ("", [], ""))

    def test_title_single_all_tags(self):
        headline, tags, tone = detect("삼성전자 기관 순매수. 연기금 순매수")
        self.assertEqual(headline, "기관 순매수 이슈")
        self.assertEqual(tags, ["기관순매수", "연기금순매수"])
        self.assertEqual(tone, "positive")
