import unittest

from backend.analysis.news.scoring import score_stock_news


class StockNewsLanguageFilterTests(unittest.TestCase):
    def _article(self, title, description=""):
        return {
            "title": title,
            "description": description,
            "published_at": "2026-10-09T00:00:00+00:00",
            "movement_signals": [],
            "issues": [],
            "themes": [],
        }

    def test_us_stock_keeps_english_only_article(self):
        result = score_stock_news(
            [self._article("Nvidia raises guidance on strong AI demand")],
            "엔비디아",
        )
        self.assertEqual(len(result), 1)

    def test_domestic_stock_still_filters_english_only_article(self):
        result = score_stock_news(
            [self._article("Samsung Electronics raises guidance")],
            "삼성전자",
        )
        self.assertEqual(result, [])

    def test_us_stock_still_keeps_korean_article(self):
        result = score_stock_news(
            [self._article("엔비디아, AI 수요 증가에 가이던스 상향")],
            "엔비디아",
        )
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
