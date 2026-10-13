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


if __name__ == "__main__":
    unittest.main()
