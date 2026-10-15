"""AI candidate selection must not alter displayed news or trust snippets."""
import unittest

from backend.services.news_ai_candidates import select_verified_ai_candidates


class VerifiedAICandidateTests(unittest.TestCase):
    def article(self, index, topic="공장건설", *, source="jsonld_article_body",
                url=None, body=None):
        return {
            "title": "SK하이닉스 뉴스 %d" % index,
            "storyboard_keyword": topic,
            "url": url or "https://example.org/story?article=%d" % index,
            "published_at": "2026-10-15T16:30:00+09:00",
            "storyboard_time": "16:30",
            "_central_checked_full_text": (
                body if body is not None else
                "SK하이닉스가 공시한 사항을 해당 기사에서 설명한다. 확인된 사실과 발표 내용만 기록한다. " * 2
            ),
            "_central_checked_source": source,
        }

    def test_diverse_topics_first_then_repeat_material_when_room(self):
        rows = [self.article(i) for i in range(8)]
        rows.extend(self.article(8+i, topic=topic) for i, topic in
                    enumerate(["미국CPI", "외국인매도", "반도체규제", "실적", "신제품"]))
        selected = select_verified_ai_candidates(rows)
        self.assertEqual(len(selected), 10)
        ids = [int(x["url"].split("=")[-1]) for x in selected]
        # Don't allow eight factory reports to hide all other material topics.
        self.assertEqual(ids[:6], [0, 8, 9, 10, 11, 12])
        self.assertEqual(ids[6:], [1, 2, 3, 4])
        self.assertEqual(len(rows), 13)
        self.assertTrue(all("_central_checked" not in x for x in selected))

    def test_same_topic_distinct_events_are_not_discarded(self):
        rows = [self.article(1, body="SK하이닉스 미국 공장에 신규 투자를 발표했다. " * 3),
                self.article(2, body="SK하이닉스 중국 생산 장비 허가를 신청했다. " * 3)]
        self.assertEqual(len(select_verified_ai_candidates(rows)), 2)

    def test_query_tracking_duplicate_but_distinct_ids_not_collapsed(self):
        rows = [self.article(1, url="https://site.kr/read?aid=1&utm_source=naver"),
                self.article(2, url="https://site.kr/read?utm_source=other&aid=1"),
                self.article(3, url="https://site.kr/read?aid=2")]
        selected = select_verified_ai_candidates(rows)
        self.assertEqual(len(selected), 2)
        self.assertEqual([x["title"] for x in selected],
                         ["SK하이닉스 뉴스 1", "SK하이닉스 뉴스 3"])

    def test_meta_only_and_unverified_page_are_not_sent(self):
        rows = [
            self.article(1, source="meta_description"),
            self.article(2, source="all_page_paragraphs"),
            self.article(3, source="fetch_failed"),
            self.article(4, body="짧음"),
            self.article(5, source="article_or_main_paragraphs"),
        ]
        out = select_verified_ai_candidates(rows)
        self.assertEqual([x["title"] for x in out], ["SK하이닉스 뉴스 5"])

    def test_at_most_ten_and_does_not_mutate_display_inputs(self):
        rows = [self.article(i, topic=str(i)) for i in range(30)]
        snapshot = [(x["title"], x["_central_checked_source"],
                     x["_central_checked_full_text"]) for x in rows]
        self.assertEqual(len(select_verified_ai_candidates(rows, limit=40)), 10)
        self.assertEqual(len(select_verified_ai_candidates(rows, limit=0)), 0)
        self.assertEqual(
            [(x["title"], x["_central_checked_source"], x["_central_checked_full_text"])
             for x in rows], snapshot)


if __name__ == "__main__":
    unittest.main()
