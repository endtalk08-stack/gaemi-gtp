"""Exact active stock recognition (KR/US); no provider, AI or network calls."""
import unittest

from backend.analysis.news.scoring import build_connected_keyword_test


class DynamicSelectedStockOwnerTests(unittest.TestCase):
    def _first(self, name, title, description=""):
        return build_connected_keyword_test([{
            "title": title, "description": description,
        }], name)["articles"][0]

    def test_ht_robotics_owns_explicit_manufacturing_event(self):
        row = self._first(
            "HT로보틱스", "HT로보틱스, ESS 양산 개시 및 생산 확대",
            "HT로보틱스가 로봇 부품 양산을 시작했다.",
        )
        self.assertTrue(row["keywords"])
        self.assertEqual(row["event_owner"], "HT로보틱스")
        self.assertEqual(row["relation_type"], "direct")

    def test_ht_robotics_owns_live_headline_ess_event(self):
        row = self._first(
            "HT로보틱스", "HT로보틱스 거래량 2559만주…로봇·ESS 양산 일정 관심",
            "HT로보틱스의 ESS 관련 양산 일정이 주목받고 있다.",
        )
        self.assertTrue(row["keywords"])
        self.assertEqual(row["event_owner"], "HT로보틱스")
        self.assertEqual(row["relation_type"], "direct")

    def test_mention_without_event_remains_mention_only(self):
        row = self._first(
            "HT로보틱스", "경북 피지컬AI 특구 추진",
            "HT로보틱스가 참여 기업으로 소개됐다.",
        )
        self.assertEqual(row["keywords"], [])
        self.assertEqual(row["relation_type"], "mention_only")

    def test_other_company_event_is_not_stolen(self):
        row = self._first(
            "HT로보틱스", "삼성전자 매출 확대, HT로보틱스는 동향 점검",
            "삼성전자가 매출 증가를 발표했다. HT로보틱스는 별도 소식이 없었다.",
        )
        self.assertTrue(row["keywords"])
        self.assertEqual(row["event_owner"], "삼성전자")
        self.assertEqual(row["relation_type"], "indirect")

    def test_new_us_stock_owns_its_sourced_contract(self):
        row = self._first(
            "Orion Quantum", "Orion Quantum signs supply agreement",
            "Orion Quantum signed a supply contract with a customer.",
        )
        self.assertIn("공급계약", row["keywords"])
        self.assertEqual(row["event_owner"], "Orion Quantum")
        self.assertEqual(row["relation_type"], "direct")

    def test_short_unknown_symbol_requires_token_boundary(self):
        row = self._first(
            "QZ", "QZX suppliers sign agreement",
            "QZX announced a supply agreement for its customers.",
        )
        self.assertEqual(row["event_owner"], "")
        self.assertEqual(row["relation_type"], "mention_only")

    def test_existing_alias_stays_with_its_catalog_company(self):
        row = self._first(
            "META", "META revenue grows",
            "Meta Platforms posted revenue gains.",
        )
        self.assertTrue(row["keywords"])
        self.assertEqual(row["event_owner"], "메타")
        self.assertEqual(row["relation_type"], "indirect")


if __name__ == "__main__":
    unittest.main()
