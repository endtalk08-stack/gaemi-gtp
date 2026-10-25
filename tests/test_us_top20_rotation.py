"""Offline regression of 5-minute, one-stock-per-tick top-20 rotation."""
import json
import unittest

from backend.services.us_top20_rotation import (
    RankingUnavailable, normalize_ranking, plan_tick, finish_tick,
)


def rows():
    return [
        {"rank": i, "symbol": f"T{i:02d}", "display_name": f"Stock {i:02d}"}
        for i in range(1, 21)
    ]


def step(state, ranking, ok=True):
    item, pending = plan_tick(state, ranking)
    next_state = finish_tick(pending, item["symbol"], ok=ok)
    return item, next_state


class RotationTests(unittest.TestCase):
    def test_exactly_20_in_rank_order_and_wraps(self):
        state = None
        seen = []
        for _ in range(40):
            item, state = step(state, rows())
            seen.append(item["symbol"])
        expected = [f"T{i:02d}" for i in range(1, 21)]
        self.assertEqual(seen, expected + expected)
        self.assertEqual(state["cycle_number"], 2)
        self.assertEqual(state["next_index"], 20)

    def test_rank_two_and_three_swap_applies_only_after_full_cycle(self):
        ranked = rows()
        swapped = rows()
        swapped[1], swapped[2] = swapped[2], swapped[1]
        swapped[1]["rank"], swapped[2]["rank"] = 2, 3
        state = None
        first = []
        for i in range(20):
            item, state = step(state, ranked if i < 2 else swapped)
            first.append(item["symbol"])
        self.assertEqual(first, [f"T{i:02d}" for i in range(1, 21)])
        second = []
        for i in range(20):
            item, state = step(state, swapped)
            second.append(item["symbol"])
        self.assertEqual(second[:4], ["T01", "T03", "T02", "T04"])
        self.assertEqual(len(set(second)), 20)

    def test_new_entry_and_exiting_stock_change_only_next_cycle(self):
        state = None
        new_rank = rows()
        new_rank[-1] = {"rank": 20, "symbol": "NEW", "display_name": "New stock"}
        for _ in range(20):
            item, state = step(state, rows() if state is None else new_rank)
        self.assertEqual(state["last_attempt"]["symbol"], "T20")
        item, state = step(state, new_rank)
        self.assertEqual(item["symbol"], "T01")
        for _ in range(18):
            _, state = step(state, new_rank)
        item, state = step(state, new_rank)
        self.assertEqual(item["symbol"], "NEW")

    def test_reboot_retries_pending_slot_before_advancing(self):
        item, state = plan_tick(None, rows())
        self.assertEqual(item["symbol"], "T01")
        restored = json.loads(json.dumps(state))
        same, restored = plan_tick(restored, list(reversed(rows())))
        self.assertEqual(same["symbol"], "T01")
        restored = finish_tick(restored, "T01", ok=True)
        following, restored = plan_tick(restored, rows())
        self.assertEqual(following["symbol"], "T02")

    def test_bad_ranking_does_not_skip_or_invent_tickers(self):
        with self.assertRaises(RankingUnavailable):
            plan_tick(None, rows()[:19])
        state = None
        for _ in range(20):
            _, state = step(state, rows())
        # A provider outage reuses the previous complete ranking in order.
        item, state = step(state, [])
        self.assertEqual(item["symbol"], "T01")

    def test_failure_advances_but_is_logged_for_next_round(self):
        first, state = step(None, rows(), ok=False)
        self.assertEqual(first["symbol"], "T01")
        self.assertEqual(state["failures"], ["T01"])
        item, state = step(state, rows())
        self.assertEqual(item["symbol"], "T02")
        for _ in range(18):
            _, state = step(state, rows())
        item, state = step(state, rows())
        self.assertEqual(item["symbol"], "T01")
        self.assertNotIn("T01", state["failures"])

    def test_rank_data_duplicate_or_gap_is_rejected(self):
        duplicate = rows()
        duplicate[1]["symbol"] = "T01"
        with self.assertRaises(RankingUnavailable):
            normalize_ranking(duplicate)
        gap = rows()
        gap[1]["rank"] = 3
        with self.assertRaises(RankingUnavailable):
            normalize_ranking(gap)

    def test_invalid_finished_pending_attempt_does_not_change_cursor(self):
        item, state = plan_tick(None, rows())
        with self.assertRaises(ValueError):
            finish_tick(state, "T02", ok=True)
        self.assertEqual(state["next_index"], 0)
        self.assertEqual(state["pending"], item["symbol"])


if __name__ == "__main__":
    unittest.main()
