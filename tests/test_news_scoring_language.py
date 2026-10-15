import unittest

from backend.analysis.news.scoring import (
    score_stock_news, _detail_phrase_matches, _detail_token_variants,
    _detail_phrase_parts, _DETAIL_SHORT_MODIFIERS,
)


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

    def test_phrase_fastpath_keeps_old_matches_for_korean_and_english(self):
        # Reference implementation from before the performance-only change.
        def reference(text, phrase, words, word_variants):
            haystack = str(text or "").lower()
            needle = str(phrase or "").strip().lower()
            if not needle:
                return False
            if needle in haystack:
                return True
            expected = _detail_phrase_parts(needle)
            if len(expected) < 2:
                return False
            expected_variants = tuple(_detail_token_variants(part) for part in expected)
            for start in range(len(words)):
                word_index = start
                matched = True
                for variants in expected_variants:
                    while word_index < len(words) and words[word_index] in _DETAIL_SHORT_MODIFIERS:
                        word_index += 1
                    if word_index >= len(words):
                        matched = False
                        break
                    actual_variants = word_variants[word_index]
                    if not any(left == right for left in actual_variants for right in variants):
                        matched = False
                        break
                    word_index += 1
                if matched:
                    return True
            return False

        texts = (
            "삼성전자가 공급 계약을 체결했다",
            "삼성전자가 공급 계약으로 매출 확대",
            "삼성전자, 새로운 공급 계약 체결",
            "삼성전자 반도체 수요가 크게 증가",
            "한국은행 금리 부담 완화",
            "the company announced data center demand and growth",
            "기업의 생산 능력은 크게 확대됐다",
            "정확한 기사 근거가 없는 시장 전망",
            "단어만으로는 확인할 수 없다",
            "",
        )
        phrases = (
            "공급 계약", "공급 확대", "생산 능력", "금리 부담",
            "data center", "data center demand", "AI 반도체",
            "기업 생산", "회사 투자", "없는 단어", "계약",
        )
        for text in texts:
            lower = text.lower()
            words = tuple(part for part in lower.split() if part)
            variants = tuple(_detail_token_variants(word) for word in words)
            available = frozenset(part for group in variants for part in group)
            for phrase in phrases:
                with self.subTest(text=text, phrase=phrase):
                    before = reference(lower, phrase, words, variants)
                    after = _detail_phrase_matches(lower, phrase, words, variants, available)
                    self.assertEqual(before, after)

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
