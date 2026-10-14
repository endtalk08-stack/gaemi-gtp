"""Regression tests for central article-body excerpts only."""

import unittest
from unittest.mock import patch

from backend.services.issue_briefs import _article_excerpt, build_issue_briefs, central_material_brief_supported
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

    def test_general_material_gate_drops_price_only_and_topicless_reports(self):
        price_only = (
            "[잠포스트] 전진홍 기자 = 13일 오후 1시29분 기준 유가증권시장에서 "
            "두산에너빌리티는 전 거래일보다 2,400원 내린 6만9100원에 거래됐다. "
            "등락률은 -3.36%였다. 이날 고가는 7만600원, 저가는 6만7300원으로 "
            "장중 변동폭은 3300원이었다."
        )
        cleaned = _article_excerpt(price_only)
        self.assertTrue(cleaned.startswith("13일 오후 1시29분 기준"))
        self.assertFalse(central_material_brief_supported(cleaned))
        self.assertFalse(central_material_brief_supported(
            "기업 관계자들이 향후 전망을 논의했다. 추후 내용을 다시 공개할 예정이다."
        ))

    def test_business_actions_are_kept_even_with_price_reaction(self):
        samples = (
            "두산에너빌리티는 A사와 300억원 공급 계약을 체결했다. "
            "오후 1시 기준 주가는 전 거래일 대비 2% 상승해 거래됐다. 등락률이 높아졌다.",
            "삼성전자는 평택 공장을 증설한다고 발표했다. "
            "생산라인 확장에 나설 계획이다.",
            "애플은 신형 제품을 공개하고 다음 달 출시할 예정이다. "
            "신제품 관련 정보가 공개됐다.",
            "현대차는 인도에 155억 달러를 투자하기로 밝혔다. "
            "현지 생산시설도 확대할 계획이다.",
        )
        for body in samples:
            with self.subTest(body=body[:35]):
                self.assertTrue(central_material_brief_supported(body), body)

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

    def test_generic_press_credits_are_removed_without_newsroom_exceptions(self):
        prefixes = (
            "[파이낸셜뉴스 뉴델리(인도)=김동호 기자] ",
            "[잠포스트] 전진홍 기자 = ",
            "【서울=뉴시스】김은정 기자= ",
            "[서울(한국)=비즈워치] 정민석 특파원 : ",
            "한국경제 홍길동 기자 = ",
            "[매일경제] ",
            "【연합뉴스】 ",
            "[파이낸셜뉴스 뉴델리(인도)=김동호 기자] "
            "【뉴시스】홍길동 기자= ",
        )
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.assertEqual(_article_excerpt(prefix + CELLTRION_BODY), CELLTRION_BODY)
                brief = build_issue_briefs(
                    [self._source_row()], "셀트리온", body_texts=[prefix + CELLTRION_BODY],
                )[0]
                self.assertEqual(brief["summary"], CELLTRION_BODY)

    def test_article_facts_and_in_body_reporter_mentions_remain(self):
        factual = (
            "삼성전자는 HBM 제품의 신규 공급계약을 체결했다고 밝혔다. "
            "이후 김영수 기자는 다른 행사에서 회사의 신제품 발표를 취재했다. "
            "차세대 제품의 출시 일정은 다음 달 공개될 예정이다."
        )
        self.assertEqual(_article_excerpt("【서울=뉴스1】박영수 기자= " + factual), factual)
        topic = (
            "[HBM] 삼성전자는 차세대 메모리 제품의 생산을 확대했다. "
            "회사는 올해 추가 생산라인을 구축할 계획이라고 밝혔다."
        )
        self.assertEqual(_article_excerpt(topic), topic)

    def test_news_agency_and_reporter_mentions_inside_body_are_kept(self):
        body = (
            "삼성전자는 신제품 생산을 확대하겠다고 밝혔다. "
            "연합뉴스는 후속 기사에서 박초롱 기자가 취재 내용을 설명했다고 전했다."
        )
        self.assertEqual(_article_excerpt(body), body)

    def test_ai_notice_translation_credit_and_reporter_prefix_removed(self):
        body = (
            "엔비디아는 중국 데이터센터용 AI 칩 시장의 점유율이 줄었다고 밝혔다. "
            "중국 기업들이 자체 AI 칩 공급을 확대했다. "
            "미국 정부의 대중국 수출 규제가 시장에 영향을 줬다. "
            "다음 분기 상황은 아직 불확실하다."
        )
        notice = (
            "AI가 자동 생성한 요약으로 정확하지 않을 수 있어요. "
            "이 기사는 인공지능(AI) 번역을 바탕으로 전문 기자들의 검증과 분석을 거쳐 "
            "생성된 콘텐츠로 원문은 10월 13일 로이터통신 기사입니다. "
            "[시드니=뉴스핌] 권지언 특파원 = "
        )
        expected = (
            "엔비디아는 중국 데이터센터용 AI 칩 시장의 점유율이 줄었다고 밝혔다. "
            "중국 기업들이 자체 AI 칩 공급을 확대했다. "
            "미국 정부의 대중국 수출 규제가 시장에 영향을 줬다."
        )
        self.assertEqual(_article_excerpt(notice + body), expected)
        briefs = build_issue_briefs(
            [self._source_row()], "엔비디아", body_texts=[notice + body]
        )
        self.assertEqual(briefs[0]["summary"], expected)

    def test_prefix_cleanup_handles_reporter_credit_before_notice(self):
        lead = (
            "(서울=연합뉴스) 홍길동 기자 = "
            "AI가 자동 생성한 요약으로 정확하지 않을 수 있어요. "
            "[시드니=뉴스핌] 권지언 특파원 = "
        )
        self.assertEqual(_article_excerpt(lead + CELLTRION_BODY), CELLTRION_BODY)

    def test_genuine_ai_reporting_and_later_credits_are_preserved(self):
        body = (
            "삼성전자는 인공지능(AI) 번역 기술 투자를 확대한다고 밝혔다. "
            "연합뉴스 박초롱 기자는 새로운 사업 계획을 보도했다. "
            "인공지능 기술을 다른 제품에도 적용할 계획이다."
        )
        self.assertEqual(_article_excerpt(body), body)

    def test_embedded_ai_notes_byline_and_invisible_prefix_are_removed(self):
        body = (
            "미국의 대중국 수출 규제와 중국의 반도체 국산화 정책으로 "
            "엔비디아의 중국 점유율이 하락했다. "
            "중국 업체들은 자국 시장에서 공급을 확대하고 있다. "
            "시장 경쟁은 더욱 치열해질 것으로 전망된다. "
            "다른 내용은 다음 기사에서 다룬다."
        )
        extracted = (
            "\ufeff속보. "
            "AI가 자동 생성한 요약으로 정확하지 않을 수 있어요. "
            "이 기사는 인공지능(AI) 번역을 바탕으로 전문 기자들의 검증과 분석을 거쳐 "
            "생성된 콘텐츠로 원문은 10월 13일 로이터통신 기사입니다. "
            "[시드니=뉴스핌] 권지언 특파원 = " + body
        )
        expected = (
            "미국의 대중국 수출 규제와 중국의 반도체 국산화 정책으로 "
            "엔비디아의 중국 점유율이 하락했다. "
            "중국 업체들은 자국 시장에서 공급을 확대하고 있다. "
            "시장 경쟁은 더욱 치열해질 것으로 전망된다."
        )
        self.assertEqual(_article_excerpt(extracted), expected)

    def test_embedded_ai_notices_do_not_strip_factual_opening(self):
        first = "엔비디아가 AI 칩 수요 증가에 따라 생산을 확대했다. "
        rest = (
            "AI가 자동 생성한 요약으로 정확하지 않을 수 있어요. "
            "이 기사는 인공지능(AI) 번역을 바탕으로 전문 기자들의 검증과 분석을 거쳐 "
            "생성된 콘텐츠로 원문은 10월 13일 로이터통신 기사입니다. "
            "[시드니=뉴스핌] 권지언 특파원 = "
            "엔비디아는 주요 고객사에 대한 공급 계획도 발표했다. "
            "중국의 수출 규제 영향도 점검하고 있다."
        )
        expected = (
            first + "엔비디아는 주요 고객사에 대한 공급 계획도 발표했다. "
            "중국의 수출 규제 영향도 점검하고 있다."
        )
        self.assertEqual(_article_excerpt(first + rest), expected)

    def test_french_ai_company_investment_title_and_single_tag(self):
        body = (
            "엔비디아가 프랑스 인공지능 기업들에 대한 투자에 나서면서 "
            "젠슨 황 최고경영자의 사업 전략이 반도체 공급을 넘어 다양한 산업으로 확장되고 있다. "
            "엔비디아는 프랑스 AI 스타트업 미스트랄에 투자한다고 밝혔다. "
            "회사는 추가 협력 사업도 검토하고 있다."
        )
        brief = build_issue_briefs(
            [self._source_row()], "엔비디아", body_texts=[body]
        )[0]
        self.assertEqual(brief["headline"], "프랑스 AI 기업 투자 이슈")
        self.assertEqual(brief["tags"], ["AI투자"])
        self.assertEqual(brief["summary"], body)

    def test_generic_ai_investment_is_grounded(self):
        body = (
            "엔비디아는 AI에 투자한다고 밝혔다. "
            "회사는 신규 사업 확대를 검토하고 있다."
        )
        brief = build_issue_briefs(
            [self._source_row()], "엔비디아", body_texts=[body]
        )[0]
        self.assertEqual(brief["headline"], "AI 투자 이슈")
        self.assertEqual(brief["tags"], ["AI투자"])

    def test_ai_mentions_without_investment_do_not_create_ai_investment_tag(self):
        body = (
            "엔비디아의 인공지능 기술 개발은 여러 분야에서 주목받고 있다. "
            "엔비디아는 신규 기술 시연 행사를 열었다."
        )
        brief = build_issue_briefs(
            [self._source_row()], "엔비디아", body_texts=[body]
        )[0]
        self.assertNotIn("AI투자", brief["tags"])
        self.assertNotIn("투자 이슈", brief["headline"])

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

    def test_hyundai_india_investment_title_and_tag_from_visible_body(self):
        bodies = [
            "정의선 현대차그룹 회장이 인도 뉴델리에서 나렌드라 모디 총리를 만났다. "
            "현대차그룹은 올해부터 7년간 약 155억 달러를 인도에 투자할 계획이다. "
            "신공장 건설과 연구개발 인프라 확충이 주요 투자 분야다.",
            "현대차그룹은 2032년까지 인도에 155억달러를 투자해 생산능력을 "
            "확충하겠다는 전략을 밝혔다. 정의선 회장은 나렌드라 모디 총리와 면담했다.",
            "정의선 현대차그룹 회장이 인도 연 140만대 생산체제를 발표하며 "
            "현지 투자 확대 계획을 밝혔다. 올해부터 7년간 약 "
            "155억달러(약 20조8000억원) 규모의 투자를 추진한다.",
        ]
        for body in bodies:
            with self.subTest(body=body[:40]):
                brief = build_issue_briefs(
                    [self._source_row()], "현대차", body_texts=[body],
                )[0]
                self.assertEqual(brief["headline"], "인도 155억 달러 투자 이슈")
                self.assertIn("인도투자", brief["tags"])
                self.assertEqual(brief["summary"], body)

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



    def test_broker_target_cut_with_decimal_percent_uses_report_decision(self):
        body = (
            "한화투자증권 연구원은 14일 보고서에서 삼성중공업의 3분기 실적이 "
            "시장 기대치에 부합할 것으로 전망했다. "
            "다만 상선 부문의 성장 둔화 우려를 반영해 목표주가를 기존 "
            "4만원에서 3만5000원으로 12.5% 하향 조정했다. "
            "부유식 데이터센터 신규 수주에 따른 성장 가능성을 긍정적으로 "
            "평가하며 투자의견 ‘매수’를 유지했다."
        )
        brief = build_issue_briefs(
            [self._source_row()], "삼성중공업", body_texts=[body]
        )[0]
        self.assertEqual(brief["headline"], "증권사 목표주가 하향 이슈")
        self.assertEqual(brief["tags"], ["목표주가하향", "매수의견유지", "실적전망"])
        self.assertEqual(brief["summary"], body)

    def test_broker_target_raise_from_article_overrides_unrelated_upstream_keyword(self):
        body = (
            "하나증권은 삼성SDI의 목표주가를 80만원에서 94만원으로 상향 조정했다. "
            "투자의견 '매수'는 유지했다."
        )
        row = dict(self._source_row(), storyboard_keywords=["공급계약", "외국인매도"])
        brief = build_issue_briefs([row], "삼성SDI", body_texts=[body])[0]
        self.assertEqual(brief["headline"], "증권사 목표주가 상향 이슈")
        self.assertEqual(brief["tags"], ["목표주가상향", "매수의견유지"])
        self.assertEqual(brief["summary"], body)

    def test_new_concrete_article_subject_can_supply_unlisted_display_keyword(self):
        body = (
            "회사는 차세대 배터리 재활용 표준 인증을 획득했다. "
            "관련 절차를 마무리했다고 밝혔다."
        )
        brief = build_issue_briefs([self._source_row()], "삼성SDI", body_texts=[body])[0]
        self.assertEqual(brief["headline"], "차세대 배터리 재활용 표준 인증 획득 이슈")
        self.assertEqual(brief["tags"], ["차세대배터리재활용표준인증획득"])
        self.assertEqual(brief["summary"], body)

    def test_unrelated_price_or_upstream_flow_keyword_is_not_rendered_from_article(self):
        body = (
            "회사 관계자들이 향후 계획에 대해 논의했다. "
            "구체적인 일정은 아직 정해지지 않았다."
        )
        row = dict(self._source_row(), storyboard_keywords=["외국인매도"])
        brief = build_issue_briefs([row], "삼성SDI", body_texts=[body])[0]
        self.assertEqual(brief["headline"], "기사 주요 내용")
        self.assertEqual(brief["tags"], [])


if __name__ == "__main__":
    unittest.main()
