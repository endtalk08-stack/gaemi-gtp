"""Regression tests for central article-body excerpts only."""

import unittest
from unittest.mock import patch

from backend.services.issue_briefs import _article_excerpt, build_issue_briefs
from backend.services.news_detail import (
    _extract_article_text_with_source,
    extract_article_text,
    read_selected_article_details,
)


CELLTRION_BODY = (
    "셀트리온은 주가 안정 및 주주가치 제고를 위해 추진해온 약 1,000억원 규모 자사주 소각 절차가 "
    "6월 4일 변경상장을 통해 최종 반영됐다고 밝혔다. "
    "이번 변경상장을 통해 최종 반영된 소각 물량은 총 48만 8,977주로, "
    "이에 따라 셀트리온 발행주식총수는 약 2억 2,163만주 수준으로 감소하게 됐다. "
    "이번 자사주 소각은 최근 공시한 약 1,000억원 규모 자사주 취득 및 전량 소각 계획의 이행 결과로, "
    "발행주식수 감소에 따른 주당순이익 개선 및 주당 가치 상승 효과가 본격화될 것으로 기대된다."
)


class CentralArticleExcerptTests(unittest.TestCase):
    def _source_row(self):
        return {
            "storyboard_time": "11:30",
            "published_at": "2026-10-13T11:30:00+09:00",
            "storyboard_keywords": ["자사주소각"],
            "article_keywords": ["자사주소각"],
            "stock_entities": ["셀트리온"],
        }

    def test_celltrion_280_characters_are_kept_verbatim(self):
        self.assertEqual(len(CELLTRION_BODY), 280)
        self.assertEqual(_article_excerpt(CELLTRION_BODY), CELLTRION_BODY)

        result = build_issue_briefs([self._source_row()], "셀트리온", body_texts=[CELLTRION_BODY])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["summary"], CELLTRION_BODY)
        self.assertEqual(result[0]["reaction_at"], "2026-10-13T11:30:00+09:00")
        self.assertNotIn("관련 이슈가 있어", result[0]["summary"])

    def test_article_byline_prefixes_are_hidden_without_changing_body(self):
        prefixes = (
            "(서울=연합뉴스) 박초롱 기자 = ",
            "[서울=뉴스1] 홍길동 기자= ",
            "연합뉴스 박초롱 기자 = ",
            "홍길동 기자 = ",
            "(서울=뉴시스) ",
        )
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.assertEqual(_article_excerpt(prefix + CELLTRION_BODY), CELLTRION_BODY)

    def test_news_agency_and_reporter_mentions_inside_body_are_kept(self):
        body = (
            "삼성전자는 신제품 생산을 확대하겠다고 밝혔다. "
            "연합뉴스는 후속 기사에서 박초롱 기자가 취재 내용을 설명했다고 전했다."
        )
        self.assertEqual(_article_excerpt(body), body)

    def test_no_article_body_means_no_central_brief(self):
        result = build_issue_briefs([self._source_row()], "셀트리온", body_texts=[""])
        self.assertEqual(result, [])

    def test_source_alignment_does_not_move_articles_after_failure(self):
        original = self._source_row()
        second = dict(original, storyboard_time="13:00", published_at="2026-10-13T13:00:00+09:00")
        result = build_issue_briefs([original, second], "셀트리온", body_texts=["", CELLTRION_BODY])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["time"], "13:00")
        self.assertEqual(result[0]["summary"], CELLTRION_BODY)

    def test_first_three_sentences_only_in_original_order(self):
        body = (
            "삼성전자가 HBM4를 양산하기 시작했다. "
            "최대 11.7Gbps의 동작 속도를 확보했다. "
            "내년 생산 능력 확대를 계획하고 있다. "
            "이후 추가 생산 계획도 검토한다."
        )
        self.assertEqual(
            _article_excerpt(body),
            "삼성전자가 HBM4를 양산하기 시작했다. "
            "최대 11.7Gbps의 동작 속도를 확보했다. "
            "내년 생산 능력 확대를 계획하고 있다.",
        )

    def test_article_html_is_trusted_body_and_meta_is_not(self):
        html = (
            b'<html><head><meta name="description" content="Just a short teaser for search listings.">'
            b'</head><article><p>Celltrion completed a treasury share cancellation involving '
            b'488,977 shares to improve shareholder value according to the company statement.</p>'
            b'</article></html>'
        )
        text, kind = _extract_article_text_with_source(html)
        self.assertEqual(kind, "article_or_main_paragraphs")
        self.assertIn("488,977 shares", text)
        self.assertEqual(extract_article_text(html), text)

    def test_meta_only_is_detected_and_not_a_verified_body(self):
        html = (
            b'<html><head><meta name="description" content="This is a search engine teaser '
            b'about a company investing in new equipment, not the actual article body.">'
            b'</head></html>'
        )
        text, kind = _extract_article_text_with_source(html)
        self.assertTrue(text)
        self.assertEqual(kind, "meta_description")
        self.assertNotIn(kind, {"jsonld_article_body", "article_or_main_paragraphs"})

    def test_selected_detail_sources_keep_text_only_backward_compatibility(self):
        rows = [{"url": "https://example.com/article"}]
        with patch("backend.services.news_detail._read_url", return_value="article text"):
            self.assertEqual(read_selected_article_details(rows), ["article text"])
        with patch(
            "backend.services.news_detail._read_url",
            return_value={"text": "article text", "source": "article_or_main_paragraphs"},
        ):
            result = read_selected_article_details(rows, with_sources=True)
        self.assertEqual(result[0]["source"], "article_or_main_paragraphs")

    def test_sec_filings_are_not_treated_as_scraped_article_bodies(self):
        rows = [{"url": "https://example.com/filing", "source_type": "sec_filing"}]
        result = read_selected_article_details(rows, with_sources=True)
        self.assertEqual(result, [{"text": "", "source": "fetch_failed"}])


    def test_diplomacy_excerpt_does_not_inherit_currency_title_or_tag(self):
        body = (
            "한·미 동맹을 외교의 축으로 삼으면서도 주변 강국과의 관계를 "
            "관리하겠다는 정부의 실용적 국익 외교가 논의되고 있다. "
            "중앙행정기관의 세종 이전은 행정수도 완성의 청사진을 보여준다. "
            "코스피는 중국발 반도체 경쟁 우려와 외국인 매도에 하락했다."
        )
        row = dict(self._source_row(), storyboard_keywords=["원화강세"])
        brief = build_issue_briefs([row], "삼성전자", body_texts=[body])[0]
        self.assertEqual(brief["summary"], body)
        self.assertEqual(brief["headline"], "한미 동맹 이슈")
        self.assertEqual(brief["tags"], ["한미동맹", "국익외교", "행정수도"])
        self.assertNotIn("원화강세", brief["tags"])

    def test_semiconductor_excerpt_does_not_inherit_foreign_sell_topic(self):
        body = (
            "인공지능(AI) 반도체 시장의 성장세가 이어지는 가운데 스마트폰 수요 둔화로 "
            "전자부품 업계의 희비가 엇갈리고 있다. "
            "AI 서버용 기판은 공급 부족이 지속되고 있으며 스마트폰 부품업체는 수요 부진에 직면했다. "
            "국내 증시가 급락하며 관련 업체에도 하락 압력이 나타났다."
        )
        row = dict(self._source_row(), storyboard_keywords=["외국인매도"])
        brief = build_issue_briefs([row], "삼성전자", body_texts=[body])[0]
        self.assertEqual(brief["summary"], body)
        self.assertEqual(brief["headline"], "AI 반도체 이슈")
        self.assertEqual(brief["tags"], ["AI반도체", "스마트폰수요둔화", "AI서버"])
        self.assertNotIn("외국인매도", brief["tags"])

    def test_celltrion_excerpt_title_and_tags_follow_body(self):
        row = dict(self._source_row(), storyboard_keywords=["원화강세"])
        brief = build_issue_briefs([row], "셀트리온", body_texts=[CELLTRION_BODY])[0]
        self.assertEqual(brief["headline"], "자사주 소각 이슈")
        self.assertIn("자사주소각", brief["tags"])
        self.assertNotIn("원화강세", brief["tags"])
        self.assertEqual(brief["summary"], CELLTRION_BODY)

    def test_no_supported_topic_uses_neutral_title_without_false_hashtags(self):
        body = (
            "관계자들이 어제 발표된 다양한 현안과 일정을 검토했다. "
            "회의에서 논의된 내용은 추후 검토를 거쳐 다시 발표하기로 했다."
        )
        row = dict(self._source_row(), storyboard_keywords=["외국인매도"])
        brief = build_issue_briefs([row], "셀트리온", body_texts=[body])[0]
        self.assertEqual(brief["headline"], "기사 주요 내용")
        self.assertEqual(brief["tags"], [])
        self.assertEqual(brief["summary"], body)

    def test_known_label_fallback_still_requires_visible_body_evidence(self):
        body = (
            "회사가 차세대 AI 데이터센터를 구축할 계획이라고 설명했다. "
            "구체적인 설치 일정은 내년에 공개할 예정이다."
        )
        row = dict(self._source_row(), storyboard_keywords=["원화강세"])
        brief = build_issue_briefs([row], "삼성전자", body_texts=[body])[0]
        self.assertEqual(brief["headline"], "AI 데이터센터 이슈")
        self.assertEqual(brief["tags"], ["AI데이터센터"])
        self.assertNotIn("원화강세", brief["tags"])
        self.assertEqual(brief["summary"], body)

    def test_legacy_call_uses_existing_headline_and_keywords(self):
        row = dict(self._source_row(), storyboard_keywords=["자사주소각"])
        brief = build_issue_briefs([row], "셀트리온")[0]
        self.assertEqual(brief["headline"], "자사주 소각 이슈")
        self.assertIn("자사주소각", brief["tags"])



if __name__ == "__main__":
    unittest.main()
