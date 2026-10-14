"""Focused stage-one regression tests for article-grounded company material."""

import unittest

from backend.services.company_critical_events import company_critical_title_and_tags as detect


class CompanyCriticalEventTests(unittest.TestCase):
    def test_upside_and_downside_events(self):
        cases = (
            ("삼성전자 신용등급 상향 발표", "신용등급 상향 이슈", "신용등급상향", "positive"),
            ("삼성전자 신용등급 하향 발표", "신용등급 하향 이슈", "신용등급하향", "negative"),
            ("삼성전자 회사채 전액 상환 완료", "채무 상환 완료 이슈", "채무상환완료", "positive"),
            ("삼성전자 채무불이행 발생 공시", "채무 불이행 이슈", "채무불이행", "negative"),
            ("삼성전자 자본잠식 해소", "자본잠식 해소 이슈", "자본잠식해소", "positive"),
            ("삼성전자 자본잠식 발생", "자본잠식 발생 이슈", "자본잠식", "negative"),
            ("삼성전자 감사의견 적정", "감사의견 적정 이슈", "감사의견적정", "positive"),
            ("삼성전자 감사의견 거절", "감사의견 거절 이슈", "감사의견거절", "negative"),
            ("삼성전자 거래 재개 결정", "거래 재개 이슈", "거래재개", "positive"),
            ("삼성전자 거래 정지 결정", "거래정지 이슈", "거래정지", "negative"),
            ("삼성전자 상장 유지 결정", "상장 유지 결정 이슈", "상장유지결정", "positive"),
            ("삼성전자 상장폐지 결정", "상장폐지 결정 이슈", "상장폐지결정", "negative"),
            ("삼성전자 공급 계약 해지 공시", "계약 해지 이슈", "계약해지", "negative"),
            ("삼성전자 수주 취소 통보", "수주 취소 이슈", "수주취소", "negative"),
            ("삼성전자 유상증자 결정", "유상증자 결정 이슈", "유상증자결정", "neutral"),
            ("삼성전자 유상증자 철회", "유상증자 철회 이슈", "유상증자철회", "neutral"),
        )
        for article, headline, tag, direction in cases:
            with self.subTest(article=article):
                self.assertEqual(detect(article), (headline, [tag], direction))

    def test_no_invented_or_unconfirmed_events(self):
        for article in (
            "삼성전자 신용등급 하향 가능성", "삼성전자 감사의견 거절 의혹",
            "삼성전자 부도설 사실무근", "삼성전자 계약 해지 부인",
            "삼성전자 유상증자 검토", "삼성전자 주가 급락",
            "삼성전자 CPI 예상 상회", "삼성전자 자본잠식 우려",
            "삼성전자 거래정지 가능성",
        ):
            with self.subTest(article=article):
                self.assertEqual(detect(article), ("", [], ""))

    def test_one_title_and_all_tags(self):
        self.assertEqual(
            detect("삼성전자 신용등급 상향. 회사채 전액 상환 완료"),
            ("신용등급 상향 이슈", ["신용등급상향", "채무상환완료"], "positive"),
        )


if __name__ == "__main__":
    unittest.main()
