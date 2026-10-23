"""Offline regression tests: code issue briefs must be article facts, not AI."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend.services.article_fact_keywords import (
    build_article_fact_briefs, read_us_price_change_pct,
)


def article(title, description, url="https://example.org/a", mins=10, **extra):
    return {
        "title": title, "description": description, "url": url,
        "published_at": (datetime.now(timezone.utc) - timedelta(minutes=mins)).isoformat(),
        **extra,
    }


class FactBriefsTests(unittest.TestCase):
    def test_price_direction_does_not_invent_cause_or_remove_facts(self):
        news = [
            article("모더나 암 백신, 흑색종 재발·사망 위험 42% 낮춰",
                    "모더나와 머크가 임상 3상 결과를 발표했다.", "/m"),
            article("모더나 암백신 임상정보 SNS에 조기 유출",
                    "모더나 임상정보가 발표에 앞서 공개됐다.", "/n", 15),
        ]
        for change in (-2.45, 2.45):
            briefs = build_article_fact_briefs(news, "모더나", price_change_pct=change)
            combined = " ".join(x["headline"] for x in briefs)
            self.assertIn("42%", combined)
            self.assertIn("조기 유출", combined)
            self.assertTrue(all(x["evidence_source"] == "article_title_description_price_context" for x in briefs))

    def test_uses_raw_article_words_not_stored_keyword_labels(self):
        news = [article(
            "테슬라, 설비투자 계획 250억 달러에서 200억 달러로 축소",
            "테슬라가 AI·로봇 사업 설비투자 규모를 줄였다고 밝혔다.",
            paired_keywords=["made_up_keyword"],
            article_keyword_details=[{"label": "made_up_keyword"}],
            movement_signals=[{"label": "made_up_keyword", "tone": "negative"}],
            issue_briefs=[{"headline": "AI said something else"}],
        )]
        result = build_article_fact_briefs(news, "테슬라", price_change_pct=5.0)
        self.assertEqual(len(result), 1)
        text = result[0]["headline"] + " ".join(result[0]["tags"])
        self.assertIn("250억", text)
        self.assertNotIn("made_up_keyword", text)
        self.assertNotIn("AI said", text)

    def test_does_not_infer_a_company_from_korean_stx_shipbuilding(self):
        news = [
            article("은행 연체율 상승", "STX조선해양의 기업회생절차가 영향을 미쳤다.", "/s"),
            article("시게이트, 신형 하드디스크 공급 계약 체결",
                    "시게이트가 신규 저장장치 공급 계약을 체결했다.", "/ss"),
        ]
        result = build_article_fact_briefs(news, "시게이트 테크놀로지 홀딩스")
        self.assertEqual(len(result), 1)
        self.assertIn("시게이트", result[0]["headline"])

    def test_rejects_apple_hip_and_meta_farmers(self):
        self.assertEqual(
            build_article_fact_briefs([article("애플힙 운동법 소개",
                                               "애플힙을 만들기 위한 운동이다.")], "애플"), [])
        self.assertEqual(
            build_article_fact_briefs([article("메타파머스 사업 확대",
                                               "메타파머스가 농업 로봇을 출시했다.")], "메타 플랫폼스(페이스북)"), [])

    def test_source_age_is_enforced(self):
        result = build_article_fact_briefs(
            [article("테슬라, 자동차 사업 매출 3% 감소",
                     "테슬라가 자동차 매출 감소를 발표했다.", mins=1500)],
            "테슬라",
        )
        self.assertEqual(result, [])

    def test_company_mention_is_not_the_other_company_event(self):
        news = [article("스페이스X, 엔비디아 등 130여개사와 기업 AI 공략",
                        "스페이스X가 AI 사업을 확대하는 데 엔비디아 등이 참여했다.")]
        self.assertEqual(build_article_fact_briefs(news, "엔비디아"), [])

    def test_price_only_news_is_not_an_event(self):
        news = [article("미 증시 장 초반 AAOI 8.08% 하락, AMD 3% 약세",
                        "AMD가 3.79% 하락했다.")]
        self.assertEqual(build_article_fact_briefs(news, "AMD", price_change_pct=1.6), [])

    def test_derivative_quote_is_not_tesla_event(self):
        news = [article("Binance TSLAUSDT Perpetual Trades 24/7 Around Tesla Q3 Results",
                        "Tesla stock derivatives are available all day.")]
        self.assertEqual(build_article_fact_briefs(news, "테슬라"), [])

    def test_never_calls_external_price_source_when_given_price(self):
        with patch("backend.services.article_fact_keywords.read_us_price_change_pct", side_effect=AssertionError):
            result = build_article_fact_briefs(
                [article("엔비디아, 삼성전기와 기판 공급 협력",
                         "엔비디아가 삼성전기와 공급 확대를 논의했다.")],
                "엔비디아", price_change_pct=-0.26,
            )
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
