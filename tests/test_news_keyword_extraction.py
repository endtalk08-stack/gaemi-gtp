import unittest

from backend.analysis.news.scoring import build_connected_keyword_test


class ConnectedKeywordExtractionTests(unittest.TestCase):
    def test_extracts_multiple_grounded_facts_from_one_article(self):
        result = build_connected_keyword_test([{
            "title": "현대차, 해외 진출 확대하며 공급 확대",
            "description": "현대차는 현지 수요에 맞춰 생산 확대 계획도 밝혔다.",
            "stocks": [
                {"name": "현대차", "region": "국내"},
                {"name": "기아", "region": "국내"},
            ],
        }], "현대차", max_keywords=3)

        article = result["articles"][0]
        self.assertEqual(article["keywords"], ["공급확대", "해외진출", "생산확대"])
        self.assertEqual([item["source"] for item in article["keyword_details"]], [
            "title-rule",
            "title-rule",
            "description-rule",
        ])


if __name__ == "__main__":
    unittest.main()
