"""Regression: Render never calls SEC/DART directly; DO collection stays intact."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent


class RenderDisclosureSeparationTests(unittest.TestCase):
    def test_render_routes_removed(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        for route in ("/disclosures/sec/detail", "/disclosures/dart/detail",
                      "/debug/dart/elestock", "/debug/sec/form4"):
            self.assertNotIn('@app.get("' + route + '")', source)

    def test_render_analysis_neon_only(self):
        source = (ROOT / "backend/services/engine.py").read_text(encoding="utf-8")
        analysis = source.split("def analyze_stock(", 1)[1]
        self.assertIn('read_snapshot("KR", clean_code)', analysis)
        self.assertIn('read_snapshot("US", ticker_symbol)', analysis)
        self.assertNotIn("fetch_kr_official_disclosures(", analysis)
        self.assertNotIn("fetch_us_official_filings(", analysis)

    def test_do_collectors_preserved(self):
        source = (ROOT / "backend/services/engine.py").read_text(encoding="utf-8")
        self.assertIn("def fetch_kr_official_disclosures(", source)
        self.assertIn("def fetch_us_official_filings(", source)
        collector = (ROOT / "backend/services/disclosure_transfer.py").read_text(encoding="utf-8")
        self.assertIn("def collect_once(", collector)

    def test_browser_reads_preloaded_details_only(self):
        source = (ROOT / "frontend/js/disclosures.js").read_text(encoding="utf-8")
        self.assertNotIn("/disclosures/sec/detail", source)
        self.assertNotIn("/disclosures/dart/detail", source)


if __name__ == "__main__":
    unittest.main()
