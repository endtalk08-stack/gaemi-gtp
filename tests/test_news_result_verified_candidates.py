"""Central notable-flow selection: preserve the shared news result and verify facts."""

import unittest
from unittest.mock import patch

from backend.services.news_result import build_stock_news_result


class VerifiedCandidateSelectionTests(unittest.TestCase):
    def _run(self, count=9, supported=(), secondary_only=()):
        supported = set(supported)
        secondary_only = set(secondary_only)
        items = [
            {
                "title": f"SK하이닉스 후보 기사 {i}",
                "url": f"https://example.test/news/{i}",
                "published_at": f"2026-10-12T0{i}:00:00",
                "storyboard_time": f"0{i}:00",
                "storyboard_keywords": [f"사건{i}"],
                "storyboard_keyword": f"사건{i}",
                "storyboard_selection_score": 100 - i,
                "relation_type": "direct",
                "supported": i in supported,
                "secondary_only": i in secondary_only,
            }
            for i in range(count)
        ]
        read_batches = []

        def read_details(batch, *, limit):
            read_batches.append([row["url"] for row in batch])
            self.assertLessEqual(len(batch), 3)
            return ["SK하이닉스가 주요 산업의 사업 동향을 발표했다." for _ in batch]

        def keyword_analysis(rows, stock_name, max_keywords):
            return {"articles": [
                {
                    "keywords": [],
                    "keyword_details": [],
                    "grounded_tags": [],
                    "stock_entities": [stock_name],
                    "event_owner": stock_name,
                    "relation_type": "direct",
                }
                for _ in rows
            ]}

        def build_brief(rows, stock_name, limit, *, diagnostics):
            row = rows[0]
            valid = row["supported"]
            secondary_only = row["secondary_only"]
            tag_checks = [{"tag": row["storyboard_keyword"], "chosen": valid}]
            if secondary_only:
                tag_checks.append({"tag": "부가키워드", "chosen": True})
            diagnostics.append({
                "brief_kind": "matched_hashtag" if valid or secondary_only
                else "missing_hashtag_fact",
                "tag_checks": tag_checks,
            })
            return [{
                "headline": row["storyboard_keyword"] + " 이슈",
                "summary": "구체적인 사건 설명" if valid or secondary_only
                else "해시태그와 연결되는 구체적인 내용은 확인되지 않았어.",
                "time": row["storyboard_time"],
                "tags": [row["storyboard_keyword"]],
            }]

        with (
            patch("backend.services.news_result.fetch_stock_news", return_value=items),
            patch("backend.services.news_result.score_stock_news", side_effect=lambda values, _: values),
            patch("backend.services.news_result.build_connected_keyword_test", side_effect=keyword_analysis),
            patch("backend.services.news_result.build_simple_today_news", side_effect=lambda values, *args, **kwargs: values),
            patch("backend.services.news_result.select_keyword_storyboard_news",
                  side_effect=lambda values, limit: list(reversed(values[:limit]))),
            patch("backend.services.news_result.read_selected_article_details", side_effect=read_details),
            patch("backend.services.news_result.extract_structured_article_facts", return_value={}),
            patch("backend.services.news_result.build_issue_briefs", side_effect=build_brief),
        ):
            result = build_stock_news_result("SK하이닉스", market="KR", storyboard_limit=3)
        return result, read_batches

    def test_replaces_three_failed_top_candidates_with_verified_later_ones(self):
        result, batches = self._run(supported=(3, 5, 7))
        self.assertEqual(len(result["paired_news_items"]), 9)
        self.assertEqual(len(result["storyboard_news_items"]), 3)
        # Display remains newest-first even though verification is score-first.
        self.assertEqual(
            [x["storyboard_keyword"] for x in result["storyboard_news_items"]],
            ["사건7", "사건5", "사건3"],
        )
        self.assertEqual(len(result["issue_briefs"]), 3)
        self.assertEqual(len(result["keyword_storyboard"]), 3)
        self.assertEqual([len(batch) for batch in batches], [3, 3, 3])
        self.assertNotIn("_brief_detail_text", result["storyboard_news_items"][0])

    def test_does_not_fill_missing_slots_with_empty_issue_descriptions(self):
        result, batches = self._run(count=4, supported=(1,))
        self.assertEqual(len(result["storyboard_news_items"]), 1)
        self.assertEqual(len(result["issue_briefs"]), 1)
        self.assertEqual(result["issue_briefs"][0]["summary"], "구체적인 사건 설명")
        self.assertEqual(len(result["paired_news_items"]), 4)
        self.assertEqual([len(batch) for batch in batches], [3, 1])

    def test_stops_after_three_verified_candidates(self):
        result, batches = self._run(supported=(0, 1, 2, 3, 4))
        self.assertEqual(len(result["issue_briefs"]), 3)
        self.assertEqual([len(batch) for batch in batches], [3])

    def test_secondary_tag_cannot_mask_missing_primary_issue_fact(self):
        result, batches = self._run(
            count=3, supported=(), secondary_only=(0, 1, 2),
        )
        self.assertEqual(result["issue_briefs"], [])
        self.assertEqual(result["storyboard_news_items"], [])
        self.assertEqual(len(result["paired_news_items"]), 3)
        self.assertEqual([len(batch) for batch in batches], [3])

    def test_empty_candidates_return_no_central_issues(self):
        result, batches = self._run(count=0)
        self.assertEqual(result["issue_briefs"], [])
        self.assertEqual(result["storyboard_news_items"], [])
        self.assertEqual(result["paired_news_items"], [])
        self.assertEqual(batches, [])


if __name__ == "__main__":
    unittest.main()
