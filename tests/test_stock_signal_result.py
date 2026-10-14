import unittest
from datetime import datetime, timedelta, timezone

from backend.services.stock_signal_result import build_stock_signals


NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)


def article(*, minutes=20, direct=True, verified=True, title="확인된 계약", url="https://example.com/a"):
    return {
        "title": title,
        "url": url,
        "published_at": (NOW - timedelta(minutes=minutes)).isoformat(),
        "storyboard_selection_score": 420,
        "relation_type": "direct" if direct else "indirect",
        "detail_read": verified,
        "source": "공식 발표",
    }


class StockSignalTests(unittest.TestCase):
    def test_price_move_has_evidence_but_does_not_assert_cause(self):
        item = article()
        brief = {"reaction_at": item["published_at"], "headline": "공급계약 발표", "summary": "실제 원문에서 확인한 내용"}
        value = build_stock_signals(
            "삼성전자", {"current": 230000, "currency": "KRW", "change_pct": -5.7},
            {"storyboard_news_items": [item], "issue_briefs": [brief]}, now=NOW
        )
        self.assertEqual(value[0]["title"], "삼성전자 5.70% 하락")
        self.assertFalse(value[0]["reason_confirmed"])
        self.assertEqual(value[0]["evidence"][0]["headline"], "공급계약 발표")
        self.assertEqual(value[0]["evidence"][0]["summary"], "실제 원문에서 확인한 내용")

    def test_unverified_or_indirect_or_old_article_is_not_evidence(self):
        candidates = [
            article(verified=False),
            article(direct=False, url="https://example.com/b"),
            article(minutes=1500, url="https://example.com/c"),
        ]
        value = build_stock_signals("마이크론", {"current": 100, "change_pct": 3},
                                   {"storyboard_news_items": candidates}, now=NOW)
        self.assertEqual(value[0]["status"], "cause_unverified")
        self.assertEqual(value[0]["evidence"], [])

    def test_no_signal_on_small_move_or_missing_quote(self):
        self.assertEqual(build_stock_signals("삼성전자", {"current": 10, "change_pct": 0.09}, {}, now=NOW), [])
        self.assertEqual(build_stock_signals("삼성전자", {"current": 0, "change_pct": 4}, {}, now=NOW), [])
        self.assertEqual(build_stock_signals("삼성전자", {"current": 10, "change_pct": float("nan")}, {}, now=NOW), [])

    def test_small_observed_move_is_visible_with_clear_evidence_limit(self):
        value = build_stock_signals("삼성전자", {"current": 230000, "change_pct": 0.65},
                                   {}, now=NOW)
        self.assertEqual(len(value), 1)
        self.assertEqual(value[0]["status"], "cause_unverified")

    def test_rfc2822_news_timestamp_is_accepted(self):
        item = article()
        item["published_at"] = (NOW - timedelta(minutes=10)).strftime("%a, %d %b %Y %H:%M:%S %z")
        value = build_stock_signals("삼성전자", {"current": 100, "change_pct": 1.5},
                                   {"storyboard_news_items": [item]}, now=NOW)
        self.assertEqual(len(value[0]["evidence"]), 1)

    def test_same_timestamp_does_not_mix_another_article_summary(self):
        a = article(title="사건 A")
        b = article(title="사건 B", url="https://example.com/b")
        value = build_stock_signals("삼성전자", {"current": 100, "change_pct": 1.5},
                                   {"storyboard_news_items": [a, b],
                                    "issue_briefs": [{"reaction_at": a["published_at"], "headline": "잘못된 연결", "summary": "내용 X"}]}, now=NOW)
        self.assertEqual(len(value[0]["evidence"]), 2)
        self.assertTrue(all(not item["summary"] for item in value[0]["evidence"]))

    def test_only_three_unique_article_urls(self):
        a = [article(url=f"https://example.com/{i}") for i in range(5)]
        a.append(article(url="https://example.com/1"))
        value = build_stock_signals("엔비디아", {"current": 100, "change_pct": 2},
                                   {"storyboard_news_items": a}, now=NOW)
        self.assertEqual(len(value[0]["evidence"]), 3)
        self.assertEqual(len({i["url"] for i in value[0]["evidence"]}), 3)


if __name__ == "__main__":
    unittest.main()
