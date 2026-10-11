"""Verify that the original top-three news selection only hides empty core briefs."""

import unittest
from unittest.mock import patch

from backend.services.news_result import build_stock_news_result


class NotableFlowCoreFactsTests(unittest.TestCase):
    def _run(self, count=6, supported=()):
        supported = set(supported)
        rows = [
            {
                "title": f"SK하이닉스 뉴스 {i}",
                "url": f"https://example.test/story/{i}",
                "published_at": f"2026-10-12T0{i}:00:00",
                "storyboard_time": f"0{i}:00",
                "storyboard_keyword": f"사건{i}",
                "storyboard_keywords": [f"사건{i}"],
                "relation_type": "direct",
                "index": i,
            }
            for i in range(count)
        ]
        read_batches = []

        def keyword_analysis(items, stock_name, max_keywords=3):
            return {"articles": [
                {
                    "keywords": [item["storyboard_keyword"]],
                    "keyword_details": [],
                    "grounded_tags": [],
                    "stock_entities": [stock_name],
                    "event_owner": stock_name,
                    "relation_type": "direct",
                }
                for item in items
            ]}

        def reader(items, *, limit):
            read_batches.append([row["index"] for row in items])
            return ["실제 기사에서 확인한 내용" for _ in items[:limit]]

        def brief_builder(items, stock_name, limit, *, diagnostics):
            emitted = []
            for rank, row in enumerate(items, 1):
                valid = row["index"] in supported
                diagnostics.append({
                    "rank": rank,
                    "emitted": True,
                    "brief_kind": "matched_hashtag" if valid
                    else "missing_hashtag_fact",
                    "tag_checks": [{"chosen": valid}],
                })
                emitted.append({
                    "headline": row["storyboard_keyword"] + " 이슈",
                    "summary": "구체적 핵심 사실" if valid
                    else "해시태그와 연결되는 구체적인 내용은 확인되지 않았어.",
                    "tags": [row["storyboard_keyword"]],
                })
            return emitted

        with (
            patch("backend.services.news_result.fetch_stock_news", return_value=rows),
            patch("backend.services.news_result.score_stock_news", side_effect=lambda items, _: items),
            patch("backend.services.news_result.build_connected_keyword_test", side_effect=keyword_analysis),
            patch("backend.services.news_result.build_simple_today_news",
                  side_effect=lambda items, *_args, **_kwargs: items),
            patch("backend.services.news_result.select_keyword_storyboard_news",
                  side_effect=lambda items, limit: items[:limit]),
            patch("backend.services.news_result.read_selected_article_details", side_effect=reader),
            patch("backend.services.news_result.extract_structured_article_facts", return_value={}),
            patch("backend.services.news_result.build_issue_briefs", side_effect=brief_builder),
        ):
            result = build_stock_news_result("SK하이닉스", market="KR")
        return result, read_batches

    def test_hides_only_missing_core_facts_from_original_three(self):
        result, batches = self._run(supported=(0, 2, 3, 4))
        self.assertEqual(len(result["paired_news_items"]), 6)
        self.assertEqual(len(result["storyboard_news_items"]), 3)
        self.assertEqual([row["summary"] for row in result["issue_briefs"]],
                         ["구체적 핵심 사실", "구체적 핵심 사실"])
        self.assertEqual(batches, [[0, 1, 2]])
        self.assertEqual(len(result["keyword_storyboard"]), 3)

    def test_does_not_backfill_from_next_articles(self):
        result, batches = self._run(supported=(3, 4, 5))
        self.assertEqual(result["issue_briefs"], [])
        self.assertEqual(len(result["storyboard_news_items"]), 3)
        self.assertEqual(batches, [[0, 1, 2]])

    def test_keeps_all_three_when_all_have_core_facts(self):
        result, batches = self._run(supported=(0, 1, 2))
        self.assertEqual(len(result["issue_briefs"]), 3)
        self.assertEqual(batches, [[0, 1, 2]])

    def test_does_not_show_missing_fact_placeholders(self):
        result, _ = self._run(supported=())
        self.assertEqual(result["issue_briefs"], [])
        self.assertEqual(len(result["paired_news_items"]), 6)

    def test_no_news_returns_empty_results(self):
        result, batches = self._run(count=0)
        self.assertEqual(result["issue_briefs"], [])
        self.assertEqual(result["storyboard_news_items"], [])
        self.assertEqual(batches, [])

    def test_a_skipped_diagnostic_does_not_shift_result_alignment(self):
        # Builder can skip a row with missing headline while still auditing it.
        from backend.services.news_result import build_stock_news_result
        source = [
            {"title": str(i), "url": f"https://example.test/{i}",
             "storyboard_keyword": f"t{i}", "storyboard_keywords": [f"t{i}"],
             "published_at": "2026-10-12T00:00:00"}
            for i in range(3)
        ]

        def briefer(items, stock, limit, *, diagnostics):
            for i in range(3):
                diagnostics.append({
                    "emitted": i != 1,
                    "brief_kind": "matched_hashtag" if i == 2 else "missing_hashtag_fact",
                    "tag_checks": [{"chosen": i == 2}],
                })
            return [{"summary": "empty"}, {"summary": "real", "headline": "t2"}]

        with (
            patch("backend.services.news_result.fetch_stock_news", return_value=source),
            patch("backend.services.news_result.score_stock_news", side_effect=lambda rows, _: rows),
            patch("backend.services.news_result.build_connected_keyword_test",
                  return_value={"articles": []}),
            patch("backend.services.news_result.build_simple_today_news",
                  side_effect=lambda rows, *_a, **_kw: rows),
            patch("backend.services.news_result.select_keyword_storyboard_news",
                  side_effect=lambda rows, limit: rows[:limit]),
            patch("backend.services.news_result.read_selected_article_details",
                  return_value=["", "", ""]),
            patch("backend.services.news_result.build_issue_briefs", side_effect=briefer),
        ):
            result = build_stock_news_result("SK하이닉스", market="KR")
        self.assertEqual(len(result["issue_briefs"]), 1)
        self.assertEqual(result["issue_briefs"][0]["summary"], "real")


if __name__ == "__main__":
    unittest.main()
