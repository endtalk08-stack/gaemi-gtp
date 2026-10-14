import datetime
import unittest
from unittest.mock import patch

from backend.analysis.news.storyboard import build_simple_today_news, select_keyword_storyboard_news


def article(
    *,
    keyword,
    tier,
    strength,
    published_at,
    flow_score=0,
    title="",
    relation_type="unknown",
    material_signal=True,
    detail_source="title-rule",
):
    return {
        "title": title,
        "storyboard_keywords": [keyword] if keyword else [],
        "storyboard_keyword_tones": {keyword: "positive"} if keyword else {},
        "article_keyword_details": (
            [{"label": keyword, "source": detail_source, "evidence": keyword}]
            if keyword else []
        ),
        "analysis_relevance_tier": tier,
        "analysis_event_strength": strength,
        "analysis_material_signal": material_signal,
        "relation_type": relation_type,
        "flow_score": flow_score,
        "flow_score_breakdown": {
            "direct_stock": 35 if tier == 3 else 0,
            "material_strength": 10,
            "movement_signal": 5,
        },
        "published_at": published_at,
    }


class NotableFlowSelectionTests(unittest.TestCase):
    def test_prefers_direct_concrete_event_over_newer_weak_mention(self):
        weak_newer = article(
            keyword="AI메모리",
            tier=1,
            strength=1,
            published_at="2026-10-07T10:30:00+00:00",
        )
        strong_older = article(
            keyword="자사주매입",
            tier=3,
            strength=4,
            published_at="2026-10-07T09:00:00+00:00",
        )

        selected = select_keyword_storyboard_news([weak_newer, strong_older], limit=1)

        self.assertEqual([item["storyboard_keyword"] for item in selected], ["자사주매입"])

    def test_keeps_only_one_event_for_the_same_keyword(self):
        older = article(
            keyword="실적상회",
            tier=3,
            strength=4,
            published_at="2026-10-07T09:00:00+00:00",
        )
        newer = article(
            keyword="실적상회",
            tier=2,
            strength=2,
            published_at="2026-10-07T10:00:00+00:00",
        )

        selected = select_keyword_storyboard_news([older, newer], limit=3)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["storyboard_keyword"], "실적상회")

    def test_returns_empty_when_no_grounded_event_exists(self):
        selected = select_keyword_storyboard_news([
            article(keyword="", tier=3, strength=5, published_at="2026-10-07T10:00:00+00:00"),
        ])

        self.assertEqual(selected, [])

    def test_keeps_syndicated_headline_rewrite_out_of_storyboard(self):
        first = article(
            keyword="실적상회",
            tier=3,
            strength=5,
            published_at="2026-10-07T10:00:00+00:00",
            title="삼성전자 3분기 실적 시장 예상치 크게 웃돌아",
        )
        rewrite = article(
            keyword="어닝서프라이즈",
            tier=3,
            strength=4,
            published_at="2026-10-07T09:55:00+00:00",
            title="삼성전자 3분기 실적 시장 예상치 대폭 상회",
        )
        separate_event = article(
            keyword="자사주매입",
            tier=3,
            strength=4,
            published_at="2026-10-07T09:50:00+00:00",
            title="삼성전자 대규모 자사주 매입 계획 발표",
        )

        selected = select_keyword_storyboard_news([first, rewrite, separate_event], limit=3)

        self.assertEqual([item["storyboard_keyword"] for item in selected], ["실적상회", "자사주매입"])
        self.assertEqual(selected[0]["published_at"], "2026-10-07T09:55:00+00:00")


    def test_numeric_rewrite_keeps_first_timestamp_and_merges_richer_fact(self):
        first = article(
            keyword="영업이익107조4,000억원",
            tier=2,
            strength=2,
            published_at="2026-10-07T09:54:00+00:00",
            title="삼성전자 올해 영업이익 107조4,000억원 전망",
        )
        first["article_keywords"] = ["영업이익107조4,000억원", "환율하락"]
        first["article_keyword_details"] = [{
            "label": "영업이익107조4,000억원",
            "evidence": "올해 영업이익 107조4,000억원 전망",
        }]

        rewrite = article(
            keyword="영업이익107조원추정",
            tier=3,
            strength=5,
            published_at="2026-10-07T10:20:00+00:00",
            title="삼성전자 연간 영업이익 107조원 추정",
        )
        rewrite["article_keywords"] = ["영업이익107조원추정", "영업이익107조4,000억원"]
        rewrite["article_keyword_details"] = [
            {
                "label": "영업이익107조원추정",
                "evidence": "연간 영업이익 107조원 추정",
            },
            {
                "label": "영업이익107조4,000억원",
                "evidence": "영업이익 107조4,000억원으로 추정",
            },
        ]

        selected = select_keyword_storyboard_news([rewrite, first], limit=3)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["published_at"], "2026-10-07T09:54:00+00:00")
        self.assertEqual(selected[0]["storyboard_keyword"], "영업이익107조4,000억원")
        self.assertIn("환율하락", selected[0]["article_keywords"])
        self.assertEqual(
            len([
                value for value in selected[0]["article_keywords"]
                if value.startswith("영업이익107조")
            ]),
            1,
        )

    def test_forecast_and_actual_profit_events_are_not_collapsed(self):
        forecast = article(
            keyword="영업이익107조원추정",
            tier=3,
            strength=5,
            published_at="2026-10-07T09:00:00+00:00",
            title="삼성전자 3분기 영업이익 107조원 전망",
        )
        actual = article(
            keyword="영업이익107조4,000억원",
            tier=3,
            strength=5,
            published_at="2026-10-07T10:00:00+00:00",
            title="삼성전자 3분기 영업이익 107조4,000억원 확정 발표",
        )

        selected = select_keyword_storyboard_news([actual, forecast], limit=3)

        self.assertEqual(len(selected), 2)


    def test_first_timestamp_is_kept_even_when_limit_is_already_full(self):
        selected_event = article(
            keyword="실적상회",
            tier=3,
            strength=6,
            published_at="2026-10-07T10:00:00+00:00",
            title="삼성전자 실적 시장 예상치 크게 웃돌아",
        )
        other_one = article(
            keyword="자사주매입",
            tier=3,
            strength=5,
            published_at="2026-10-07T09:50:00+00:00",
            title="삼성전자 자사주 매입 계획",
        )
        other_two = article(
            keyword="공급확대",
            tier=3,
            strength=5,
            published_at="2026-10-07T09:40:00+00:00",
            title="삼성전자 공급 확대 계획",
        )
        first_report = article(
            keyword="어닝서프라이즈",
            tier=1,
            strength=1,
            published_at="2026-10-07T09:00:00+00:00",
            title="삼성전자 실적 시장 예상치 대폭 상회",
        )

        selected = select_keyword_storyboard_news(
            [selected_event, other_one, other_two, first_report],
            limit=3,
        )

        earnings = next(
            item for item in selected if item["storyboard_keyword"] == "실적상회"
        )
        self.assertEqual(earnings["published_at"], "2026-10-07T09:00:00+00:00")


    def test_single_article_drops_near_duplicate_profit_amounts(self):
        source = article(
            keyword="영업이익107조원추정",
            tier=3,
            strength=5,
            published_at="2026-10-07T10:20:00+00:00",
            title="삼성전자 연간 영업이익 107조원 추정",
        )
        source["storyboard_keywords"] = [
            "영업이익107조원추정",
            "영업이익107조4,000억원",
            "환율하락",
        ]
        source["article_keywords"] = list(source["storyboard_keywords"])
        source["article_keyword_details"] = [
            {
                "label": "영업이익107조원추정",
                "evidence": "연간 영업이익 107조원 추정",
            },
            {
                "label": "영업이익107조4,000억원",
                "evidence": "영업이익 107조4,000억원으로 추정",
            },
        ]

        selected = select_keyword_storyboard_news([source], limit=3)

        self.assertEqual(selected[0]["storyboard_keyword"], "영업이익107조4,000억원")
        self.assertEqual(
            len([
                value for value in selected[0]["article_keywords"]
                if value.startswith("영업이익107조")
            ]),
            1,
        )


    def test_direct_event_beats_higher_scored_indirect_event(self):
        direct = article(
            keyword="실적전망상향",
            tier=2,
            strength=2,
            published_at="2026-10-08T09:00:00+00:00",
            relation_type="direct",
            title="Alphabet raises guidance",
        )
        indirect = article(
            keyword="HBM가격상승",
            tier=3,
            strength=8,
            published_at="2026-10-08T10:00:00+00:00",
            relation_type="indirect",
            detail_source="description-rule",
            title="삼성전자 HBM 가격 상승",
        )

        selected = select_keyword_storyboard_news([indirect, direct], limit=1)

        self.assertEqual(selected[0]["storyboard_keyword"], "실적전망상향")

    def test_mention_only_article_is_excluded_from_central_storyboard(self):
        mention = article(
            keyword="AI데이터센터",
            tier=3,
            strength=5,
            published_at="2026-10-08T10:00:00+00:00",
            relation_type="mention_only",
            title="AI 업계 동향 속 구글 언급",
        )

        selected = select_keyword_storyboard_news([mention], limit=3)

        self.assertEqual(selected, [])

    def test_other_company_title_event_stays_out_of_selected_stock_central_issue(self):
        samsung_hbm = article(
            keyword="HBM가격상승",
            tier=2,
            strength=8,
            published_at="2026-10-08T10:00:00+00:00",
            relation_type="indirect",
            material_signal=True,
            detail_source="title-rule",
            title="삼성전자 HBM 가격 상승, 구글 AI 투자 확대",
        )

        selected = select_keyword_storyboard_news([samsung_hbm], limit=3)

        self.assertEqual(selected, [])

    def test_description_level_indirect_event_stays_out_of_central_storyboard(self):
        indirect = article(
            keyword="공급부족",
            tier=2,
            strength=3,
            published_at="2026-10-08T10:00:00+00:00",
            relation_type="indirect",
            material_signal=True,
            detail_source="description-rule",
            title="AI 공급망 변화",
        )

        selected = select_keyword_storyboard_news([indirect], limit=3)

        self.assertEqual(selected, [])


    def test_news_keeps_only_items_from_the_most_recent_24_hours(self):
        class FixedDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                base = cls(2026, 10, 9, 5, 0, tzinfo=datetime.timezone.utc)
                return base.astimezone(tz) if tz else base.replace(tzinfo=None)

        recent = {
            "title": "Recent company event",
            "published_at": "2026-10-08T05:01:00+00:00",
            "article_keywords": ["제품공개"],
            "article_keyword_details": [
                {"label": "제품공개", "source": "title-official-event"}
            ],
        }
        expired = {
            "title": "Expired company event",
            "published_at": "2026-10-08T04:59:00+00:00",
            "article_keywords": ["제품공개"],
            "article_keyword_details": [
                {"label": "제품공개", "source": "title-official-event"}
            ],
        }

        with patch("backend.analysis.news.storyboard.datetime.datetime", FixedDateTime):
            us_items = build_simple_today_news(
                [recent, expired],
                "알파벳",
                limit=None,
                display_timezone="Asia/Seoul",
            )
            kr_items = build_simple_today_news(
                [recent, expired],
                "삼성전자",
                limit=None,
                display_timezone="Asia/Seoul",
            )

        self.assertEqual([item["title"] for item in us_items], ["Recent company event"])
        self.assertEqual([item["title"] for item in kr_items], ["Recent company event"])
        self.assertEqual(us_items[0]["storyboard_date"], "2026-10-08")


    def test_separate_brokerages_keep_independent_research_reports(self):
        def research(broker):
            row = article(
                keyword="목표가상향", tier=3, strength=4,
                published_at="2026-10-13T09:00:00+00:00",
                title="삼성SDI 목표주가 상향", relation_type="direct",
            )
            row["_central_checked_body"] = (
                f"{broker}은 삼성SDI의 목표주가를 84만원에서 94만원으로 "
                "상향했다. 전기차 배터리 업황 개선을 전망했다."
            )
            return row

        selected = select_keyword_storyboard_news(
            [research("신한투자증권"), research("하나증권")], limit=5,
        )
        self.assertEqual(len(selected), 2)

    def test_same_broker_same_report_from_two_publishers_still_merges(self):
        first = article(
            keyword="목표가상향", tier=3, strength=4,
            published_at="2026-10-13T09:00:00+00:00",
            title="삼성SDI 목표주가 상향", relation_type="direct",
        )
        first["_central_checked_body"] = (
            "신한투자증권은 삼성SDI의 목표주가를 94만원으로 상향했다. 실적 개선을 예상했다."
        )
        second = dict(first)
        second["published_at"] = "2026-10-13T10:00:00+00:00"
        second["source"] = "다른 언론사"
        second["_central_checked_body"] = (
            "신한투자증권은 삼성SDI의 목표주가를 940000원으로 상향했다. 실적 개선을 예상했다."
        )
        self.assertEqual(len(select_keyword_storyboard_news([first, second], limit=5)), 1)

    def test_same_broker_changed_target_price_is_distinct(self):
        def research(target):
            row = article(
                keyword="목표가상향", tier=3, strength=4,
                published_at="2026-10-13T09:00:00+00:00",
                title="삼성SDI 목표주가 상향", relation_type="direct",
            )
            row["_central_checked_body"] = (
                f"신한투자증권은 삼성SDI 목표주가를 {target}으로 상향했다."
            )
            return row

        self.assertEqual(len(select_keyword_storyboard_news(
            [research("94만원"), research("99만원")], limit=5,
        )), 2)

    def test_unattributed_business_story_keeps_existing_deduplication(self):
        row = article(
            keyword="생산확대", tier=3, strength=4,
            published_at="2026-10-13T09:00:00+00:00",
            title="삼성SDI 미국 ESS 생산 확대", relation_type="direct",
        )
        row["_central_checked_body"] = "삼성SDI는 미국에서 ESS 생산을 확대했다."
        self.assertEqual(len(select_keyword_storyboard_news(
            [row, dict(row)], limit=5,
        )), 1)


if __name__ == "__main__":
    unittest.main()
