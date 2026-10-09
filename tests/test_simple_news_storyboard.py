import unittest

from backend.analysis.news.storyboard import select_keyword_storyboard_news


def article(*, keyword, tier, strength, published_at, flow_score=0, title=""):
    return {
        "title": title,
        "storyboard_keywords": [keyword] if keyword else [],
        "storyboard_keyword_tones": {keyword: "positive"} if keyword else {},
        "analysis_relevance_tier": tier,
        "analysis_event_strength": strength,
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


if __name__ == "__main__":
    unittest.main()
