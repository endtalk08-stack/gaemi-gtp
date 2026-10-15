"""Regress Korean news press credits without erasing facts or attribution."""
import copy
import unittest

from backend.services.issue_briefs import _article_excerpt
from backend.services.news_byline import strip_leading_news_credit
from backend.services.news_result import _sanitize_news_display_briefs

BODY = (
    "삼성전자와 SK하이닉스가 인공지능(AI) 반도체 공급을 늘린다. "
    "올해 공장 투자가 확대됐다."
)

class PressCreditTests(unittest.TestCase):
    def test_real_source_and_other_publisher_representations(self):
        prefixes = [
          "| 스마트비즈 = 김혜인 기자 | ",
          "｜스마트비즈=김혜인 기자｜ ",
          "│ 스마트비즈 = 김혜인 기자 │ ",
          "스마트비즈 = 김혜인 기자 | ",
          "스마트비즈=김혜인 기자 ",
          "스마트비즈 : 김혜인 기자 ",
          "[스마트비즈 = 김혜인 기자] ",
          "【스마트비즈 = 김혜인 기자】 ",
          "[한국경제=이민정 기자] ",
          "【이데일리=최유진 특파원】 ",
          "[한경 = 김민지 수습기자] ",
          "매일경제 박지연 기자 = ",
          "연합뉴스 김지영 기자 : ",
          "머니투데이 = 김은정 기자 ",
          "디지털데일리 = 박소영 기자 ",
          "ZDNET Korea = John Kim 기자 | ",
          "[서울=뉴스1] 황진중 기자 = ",
          "(서울=뉴스1) 황진중 기자 = ",
          "【세종=뉴시스】 김준영 기자 = ",
          "[뉴스1 황진중 기자] ",
          "【매일경제 김유진 기자】 ",
          "[한국경제] 김민수 기자 = ",
          "【KBS】 김유진 기자 : ",
          "김민수 기자 = ",
          "홍길동 특파원 : "
]
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.assertEqual(strip_leading_news_credit(prefix + BODY), BODY)
                self.assertEqual(_article_excerpt(prefix + BODY), BODY)

    def test_do_not_remove_article_facts_or_topic_headlines(self):
        lines = [
          "[HBM] 반도체 수요가 확대됐다.",
          "연합뉴스는 삼성전자의 신규 투자 소식을 전했다.",
          "삼성전자 기자간담회에서 신제품을 공개했다.",
          "이 기자는 삼성전자 공급망을 점검했다.",
          "삼성전자, 스마트비즈와 데이터 공급 계약을 체결했다.",
          "【속보】 코스피가 상승했다.",
          "사진=연합뉴스 반도체 공장 신규 투자 현장이다."
]
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(strip_leading_news_credit(line), line)

    def test_existing_neon_snapshot_becomes_clean_without_changing_source_fields(self):
        original = {
            "issue_briefs": [{
                "summary": "| 스마트비즈 = 김혜인 기자 | " + BODY,
                "headline": "공장 증설 이슈",
                "tags": ["공장증설"],
            }],
            "paired_news_items": [{
                "url": "https://www.smartbizn.com/news/articleView.html?idxno=1",
                "title": "SK하이닉스 반도체 투자",
                "description": "| 스마트비즈 = 김혜인 기자 | 원본 설명은 보존",
            }],
            "_news_status": "ok",
        }
        clean = _sanitize_news_display_briefs(copy.deepcopy(original))
        self.assertEqual(clean["issue_briefs"][0]["summary"], BODY)
        self.assertEqual(clean["issue_briefs"][0]["headline"], "공장 증설 이슈")
        self.assertEqual(clean["issue_briefs"][0]["tags"], ["공장증설"])
        self.assertEqual(clean["paired_news_items"], original["paired_news_items"])
        self.assertIn("김혜인", original["issue_briefs"][0]["summary"])

    def test_idempotent_and_non_credit_summary(self):
        self.assertEqual(strip_leading_news_credit(strip_leading_news_credit(BODY)), BODY)
        self.assertEqual(_sanitize_news_display_briefs({"issue_briefs":[{"summary":BODY}]}), {"issue_briefs":[{"summary":BODY}]})

if __name__ == "__main__":
    unittest.main()
