"""Offline regression of staged US 0-3 directional materials; no external services."""
import contextlib
import importlib.util
import json
import pathlib
import sys
import unittest
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))
STAGE = ROOT / "ops/do-gateway"

def module(name, file):
    spec = importlib.util.spec_from_file_location(name, STAGE / file)
    out = importlib.util.module_from_spec(spec)
    sys.modules[name] = out
    spec.loader.exec_module(out)
    return out

groq = module("staged_daily_groq_issues", "us_materials_groq_20261023.py")
store = module("staged_ai_issue_store", "us_materials_store_20261023.py")
adapter = module("staged_ai_issue_display_adapter", "us_materials_adapter_20261023.py")
batch = module("us_materials_batch", "us_materials_batch_20261023.py")

def issue(direction="up", idx=1):
    return {"headline": "반도체 수요 확대", "summary": "매출에 긍정적이야.",
            "direction": direction, "tags": ["#반도체"], "source_ids": [idx]}

SOURCE = {"title": "공식 발표", "description": "사업 확대", "published_at":
          "2026-10-23T10:00:00+00:00", "source": "공식", "url": "https://example.com/x", "source_id": 1}

class FakeCursor:
    def __init__(self):
        self.entries = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, statement, args):
        self.entries.append((statement, args))
    def fetchone(self): return (123,)

class FakeConn:
    def __init__(self):
        self.cursor_instance = FakeCursor()
    def transaction(self): return contextlib.nullcontext()
    def cursor(self): return self.cursor_instance

class MaterialTests(unittest.TestCase):
    def test_prompt_exact_total_cap_and_direction(self):
        self.assertIn("합쳐서 0~3개", groq.PROMPT)
        self.assertIn('direction="up"', groq.PROMPT)
        self.assertIn('direction="down"', groq.PROMPT)
        self.assertIn("해시태그 1개", groq.PROMPT)

    def test_accept_zero_and_three_reject_four(self):
        self.assertEqual(groq.parse_issues('{"issues":[]}', require_direction=True), [])
        self.assertEqual(len(groq.parse_issues(json.dumps({"issues":[issue()] * 3}),
                                                require_direction=True)), 3)
        with self.assertRaises(ValueError):
            groq.parse_issues(json.dumps({"issues":[issue()] * 4}),
                              require_direction=True)

    def test_require_direction_and_one_hashtag(self):
        wrong = issue()
        del wrong["direction"]
        with self.assertRaises(ValueError):
            groq.parse_issues(json.dumps({"issues":[wrong]}), require_direction=True)
        wrong = issue("sideways")
        with self.assertRaises(ValueError):
            groq.parse_issues(json.dumps({"issues":[wrong]}), require_direction=True)
        wrong = issue()
        wrong["tags"] = ["#a", "#b"]
        with self.assertRaises(ValueError):
            groq.parse_issues(json.dumps({"issues":[wrong]}), require_direction=True)

    def test_legacy_readback_still_allowed(self):
        legacy = issue()
        del legacy["direction"]
        self.assertEqual(groq.parse_issues(json.dumps({"issues":[legacy]}))[0]["headline"], legacy["headline"])

    def test_store_bundle_retains_direction_without_schema_change(self):
        conn = FakeConn()
        saved = store.save_ai_issues(conn, [issue("down")], market="US", symbol="테슬라",
                                    exchange_day=date(2026,10,23), sources_by_issue=[[SOURCE]])
        self.assertEqual(saved, [123])
        inserts = [args for sql,args in conn.cursor_instance.entries
                   if "INSERT INTO public.news_processed_results_24h" in sql]
        self.assertEqual(len(inserts), 1)
        payload = json.loads(inserts[0][2])
        self.assertEqual(payload["issues"][0]["direction"], "down")
        self.assertNotIn("direction", conn.cursor_instance.entries[0][0])

    def test_adapter_preserves_hidden_direction(self):
        rendered = adapter.to_issue_briefs([issue("up")], "2026-10-23 10:00",
                                          ["엔비디아"], sources_by_issue=[[SOURCE]])
        self.assertEqual(rendered[0]["direction"], "up")
        self.assertEqual(rendered[0]["headline"], issue()["headline"])
        self.assertEqual(rendered[0]["tags"], ["#반도체"])

    def test_batch_surfaces_direction_without_extra_calls(self):
        conn = FakeConn()
        calls = []
        original_source = batch.issue_source_metadata
        try:
            batch.issue_source_metadata = lambda issues, articles: [[SOURCE] for _ in issues]
            def analyze(name, articles):
                calls.append(name)
                return [issue("up"), issue("down")]
            def save(db, issues, **kwargs):
                self.assertEqual([x["direction"] for x in issues], ["up","down"])
                return [11,12]
            result = batch.run_stock_batch(conn, [{
                "market":"US","symbol":"엔비디아","name":"엔비디아",
                "exchange_day":date(2026,10,23),"articles":[SOURCE]
            }],analyze=analyze,save=save,reserve=lambda *a,**kw: True,
            finish=lambda *a,**kw: True)[0]
        finally:
            batch.issue_source_metadata = original_source
        self.assertEqual(calls, ["엔비디아"])
        self.assertEqual(result["issue_directions"], ["up", "down"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
