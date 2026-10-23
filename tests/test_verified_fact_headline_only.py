"""Existing selected-news 3-sentence source must never be changed by fact titles."""
import unittest
from datetime import datetime, timezone

from backend.services.issue_briefs import _article_excerpt
from backend.services.verified_fact_headline import (
    grounded_fact_title, overlay_verified_headlines,
)


NOW = datetime.now(timezone.utc).isoformat()


class TitleOnlyOverlayTests(unittest.TestCase):
    def setUp(self):
        self.body = (
            "마이크론은 내년부터 이익에 연동된 분기별 성과급을 도입한다고 발표했다. "
            "이 제도는 회사 실적에 따라 직원에게 추가 지급하는 보상 체계다. "
            "노조는 별도의 이익공유안을 두고 회사와 협상을 진행하고 있다. "
            "네 번째 문장은 화면에 포함되면 안 된다."
        )
        self.excerpt = _article_excerpt(self.body)
        self.brief = {
            "headline": "기존 코드 키워드 제목",
            "summary": self.excerpt,
            "tags": ["이익연동성과급도입", "고객계약"],
            "stock_names": ["마이크론 테크놀로지"],
            "time": "08:26",
            "reaction_at": NOW,
        }
        self.article = {
            "title": "삼전닉스 이어 마이크론도 이익연동 성과급 도입⋯보상 경쟁",
            "description": "원래 뉴스 설명을 일부만 제공",
            "url": "https://example.org/micron-earnings",
            "published_at": NOW,
        }

    def test_changes_only_headline_and_adds_exact_selected_source(self):
        result = overlay_verified_headlines(
            [self.brief], [self.article], [self.body], "마이크론 테크놀로지",
        )
        self.assertEqual(len(result), 1)
        got = result[0]
        self.assertEqual(got["headline"], "마이크론, 이익연동 성과급 도입")
        self.assertEqual(got["summary"], self.excerpt)
        self.assertEqual(got["tags"], self.brief["tags"])
        self.assertEqual(got["stock_names"], self.brief["stock_names"])
        self.assertEqual(got["time"], self.brief["time"])
        self.assertEqual(got["reaction_at"], self.brief["reaction_at"])
        self.assertNotIn("네 번째 문장", got["summary"])
        self.assertEqual(got["summary"].count("다."), 3)
        self.assertEqual(got["source_articles"][0]["url"], self.article["url"])
        self.assertEqual(self.brief["headline"], "기존 코드 키워드 제목")
        self.assertEqual(self.article["description"], "원래 뉴스 설명을 일부만 제공")

    def test_no_verified_original_body_no_broadcast_brief(self):
        self.assertEqual(overlay_verified_headlines([self.brief], [self.article], [""],
                       "마이크론 테크놀로지"), [self.brief])

    def test_no_mismatched_original_article(self):
        unrelated = dict(self.article, url="https://example.org/unrelated")
        self.assertEqual(overlay_verified_headlines(
            [self.brief], [unrelated], ["다른 회사의 기사 원문이다. 매우 긴 본문이다. 완전히 다른 사실이다."],
            "마이크론 테크놀로지",
        ), [self.brief])

    def test_english_union_fact_in_korean_without_changing_article(self):
        title = "Micron Taoyuan Union Members Reject Profit-Sharing Proposal"
        self.assertEqual(
            grounded_fact_title(title, self.excerpt, "마이크론 테크놀로지", "기존제목"),
            "마이크론 타오위안 노조, 이익공유안 거부"
        )

    def test_english_unrealized_gain_carries_exact_money(self):
        title = "SpaceX Books $561 Million Unrealized Gain on Boring Co. Stake"
        self.assertEqual(
            grounded_fact_title(title, self.excerpt, "스페이스X", "기존제목"),
            "스페이스X, 보링컴퍼니 지분 평가이익 5억6,100만 달러"
        )

    def test_no_price_causality_generated(self):
        self.assertEqual(grounded_fact_title(
            "마이크론 주가 3.49% 상승, SK하이닉스 반등",
            self.excerpt, "마이크론 테크놀로지", "기존 팩트 제목",
        ), "기존 팩트 제목")

    def test_unchanged_order_and_three_separate_sources(self):
        sources=[]
        originals=[]
        bodies=[]
        for n in range(3):
            body=f"테슬라는 배터리 공급 계약을 발표했다. 계약 금액은 {n+1}억 달러다. 공급은 내년부터 시작된다."
            excerpt=_article_excerpt(body)
            sources.append({"title":f"테슬라, 배터리 공급 계약 {n+1}억 달러 체결",
                            "published_at":NOW,"url":f"https://example.org/{n}"})
            originals.append({"summary":excerpt,"headline":f"기존 {n}","tags":[f"키워드{n}"],"stock_names":["테슬라"]})
            bodies.append(body)
        out=overlay_verified_headlines(originals,sources,bodies,"테슬라")
        self.assertEqual([b["source_articles"][0]["url"] for b in out],
                         [s["url"] for s in sources])
        self.assertEqual([b["tags"] for b in out],[s["tags"] for s in originals])


if __name__ == "__main__":
    unittest.main()
