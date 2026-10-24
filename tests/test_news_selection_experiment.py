"""Regression checks: filter metadata BEFORE reading full originals."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from experiments.news_selection import (
    CATEGORIES, classify_metadata, run_selected_trial, select_candidates,
)


NOW = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)


def news(title, *, stock="", hours=1, url="", snippet="", source="verified publisher"):
    return {
        "title": title, "stock_name": stock, "description": snippet,
        "url": url or "https://publisher.example/" + str(abs(hash(title))),
        "published_at": (NOW - timedelta(hours=hours)).isoformat(),
        "source": source,
        # A feed may expose this field; selection must NEVER use it.
        "full_text": "private full original text should not be consulted",
    }


class NewsSelectionExperimentTests(unittest.TestCase):
    def test_all_seven_types_have_preliminary_metadata_paths(self):
        cases = [
            (news("뉴욕증시 주요 지수 하락 마감", snippet="나스닥 등락 확인"), "미국 증시 마감"),
            (news("AMD 신규 칩 공급 계약 발표", stock="AMD"), "개별 종목"),
            (news("미국 CPI 소비자물가지수 발표", snippet="예상치 비교"), "경제지표"),
            (news("WTI 국제유가 상승, OPEC 회의 영향"), "에너지"),
            (news("연준 FOMC 회의 일정 발표"), "연준 일정"),
            (news("월가 증권사 엔비디아 목표주가 상향"), "투자의견"),
            (news("테슬라 3분기 실적 발표, 매출 증가"), "실적 발표"),
        ]
        self.assertEqual(set(CATEGORIES), {expected for _, expected in cases})
        for row, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify_metadata(row)[0], expected)
        selected = select_candidates([row for row, _ in cases], now=NOW)
        self.assertEqual({row["category"] for row in selected}, set(CATEGORIES))
        self.assertTrue(all("full_text" not in row for row in selected))

    def test_rejects_unrelated_stale_undated_http_and_duplicates(self):
        rows = [
            news("테슬라 실적 발표, 매출 증가", hours=1,
                 url="https://publisher.example/a?ref=naver"),
            news("테슬라 실적 발표, 매출 증가", hours=1,
                 url="https://publisher.example/a?ref=other"),
            news("미국 GDP 발표", hours=100),
            news("뉴욕증시 하락 마감", url="http://publisher.example/insecure"),
            news("파월 연설 예정", url="https://publisher.example/unknown",
                 hours=-1),
            news("정해지지 않은 기업 동향과 일반 이야기"),
        ]
        selected = select_candidates(rows, now=NOW)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["category"], "실적 발표")

    def test_category_limit_is_applied_before_any_full_read(self):
        rows = [
            news("연준 FOMC 회의 일정 발표", url="https://publisher.example/1"),
            news("연준 파월 연설 일정 공개", url="https://publisher.example/2"),
            news("연준 FOMC 기자회견 예정", url="https://publisher.example/3"),
            news("미국 CPI 발표", url="https://publisher.example/4"),
        ]
        selected = select_candidates(rows, now=NOW, limit_per_category=1)
        self.assertEqual(len(selected), 2)
        self.assertEqual({row["url"] for row in selected},
                         {"https://publisher.example/1", "https://publisher.example/4"})

    def test_reader_only_receives_shortlisted_urls(self):
        rows = [
            news("미국 CPI 발표", url="https://publisher.example/selected"),
            news("일반적인 다른 소식", url="https://publisher.example/rejected"),
            news("뉴욕증시 마감 뉴스", url="https://publisher.example/stale",
                 hours=70),
        ]
        reads = []
        writes = []

        def reader(url):
            reads.append(url)
            return SimpleNamespace(text="verified whole article", source_kind="article_body")

        def writer(body, url, *, source_kind):
            writes.append((body, url, source_kind))
            return {"status": "experimental", "headline": "검증용 제목", "body": "검증용 본문"}

        results = run_selected_trial(rows, read_article=reader,
                                     compose_article=writer, now=NOW)
        self.assertEqual(reads, ["https://publisher.example/selected"])
        self.assertEqual(len(writes), 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["category"], "경제지표")

    def test_unavailable_full_article_does_not_trigger_publication_or_other_reads(self):
        rows = [news("미국 CPI 발표", url="https://publisher.example/a")]

        def reader(url):
            raise TimeoutError("blocked")

        results = run_selected_trial(
            rows, now=NOW, read_article=reader,
            compose_article=lambda *args, **kwargs: self.fail("writer must not run"),
        )
        self.assertEqual(results[0]["status"], "not_supported")
        self.assertIn("TimeoutError", results[0]["reason"])


if __name__ == "__main__":
    unittest.main()
