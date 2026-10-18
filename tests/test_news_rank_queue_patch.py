"""Test only the two intended scheduler replacements."""
import importlib.util
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("coverage_patch",ROOT/"ops/staged_news_rank_queue_patch.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RankedNewsQueuePatchTests(unittest.TestCase):
    def test_changes_only_ranked_feed_selection(self):
        source=('''def next_ranked_stock(fixed, state):
    try:
        current = []
        market, path = "미국", "/market/popular"
            state["ranked"] = current
            print(f"[news-worker] ranking market={market} matches={len(current)}", flush=True)
    except Exception as exc:
            state["ranked"] = []  # Never keep targeting an obsolete TOP20 feed.
            print(f"[news-worker] ranking_error={type(exc).__name__}", flush=True)
''')
        # The transform must refuse a different baseline, not edit unrelated code.
        with self.assertRaises((ValueError,IndentationError,SyntaxError)):
            m.patch_content(source)

if __name__=="__main__":
    unittest.main()
