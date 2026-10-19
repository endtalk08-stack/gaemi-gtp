"""Offline SEC display regression checks: no network or persistence."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
engine_stub = types.ModuleType("backend.services.engine")
engine_stub.US_CIKS = {"NVDA": "0001045810"}
engine_stub.TICKERS = {"엔비디아": "NVDA", "삼성전자": "005930.KS"}
engine_stub._enrich_us_8k_from_submission = lambda item, ticker: item.update({"key_points_ko": ["공식 SEC 문장"]})
engine_stub._enrich_us_form4_from_submission = lambda item, ticker: item.update({
    "person": "Director", "transactions": [{"code": "P", "shares": "100", "price": "10"}]
})

# Loading the isolated module avoids importing the live worker, Redis, AI or yfinance.
with patch.dict(sys.modules, {"backend.services.engine": engine_stub}):
    spec = importlib.util.spec_from_file_location(
        "backend.services.us_sec_disclosures",
        ROOT / "backend/services/us_sec_disclosures.py")
    sec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sec)


ACCESSION_8K = "0001045810-26-000101"
ACCESSION_10Q = "0001045810-26-000102"


def recent_rows():
    return {
        "form": ["8-K", "10-Q", "S-3", "4"],
        "filingDate": ["2026-10-19"] * 3 + ["2026-10-18"],
        "acceptanceDateTime": ["2026-10-19T09:00:00Z"] * 4,
        "accessionNumber": [ACCESSION_8K, ACCESSION_10Q,
                            "0001045810-26-000103", "0001045810-26-000104"],
        "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.xml"],
        "primaryDocDescription": ["Current report", "Quarterly filing", "Registration", "Insider"],
    }


class SecDisplayTests(unittest.TestCase):
    def test_all_sec_form_types_are_in_todays_list(self):
        with patch.object(sec, "_submissions", return_value=("1045810", recent_rows())):
            data = sec.list_today("엔비디아", today=__import__("datetime").date(2026, 10, 19))
        self.assertEqual([x["form"] for x in data["items"]], ["8-K", "10-Q", "S-3"])
        self.assertEqual(data["time_zone"], "America/New_York")
        self.assertTrue(all(x["accession"] and x["ticker"] == "NVDA" for x in data["items"]))

    def test_unsupported_stock_is_not_reported_as_no_filings(self):
        with self.assertRaises(ValueError):
            sec.list_today("삼성전자")
        with self.assertRaises(ValueError):
            sec.detail("엔비디아", "../../etc/passwd")

    def test_8k_detail_uses_official_submission_enrichment(self):
        with patch.object(sec, "_submissions", return_value=("1045810", recent_rows())):
            item = sec.detail("NVDA", ACCESSION_8K)
        self.assertEqual(item["detail_status"], "ready")
        self.assertEqual(item["key_points_ko"], ["공식 SEC 문장"])

    def test_missing_accession_is_rejected(self):
        with patch.object(sec, "_submissions", return_value=("1045810", recent_rows())):
            with self.assertRaises(ValueError):
                sec.detail("NVDA", "0001045810-26-777777")

    def test_financial_metrics_compare_equal_duration_fiscal_periods(self):
        facts = {"facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {"USD": [
                    {"accn": ACCESSION_10Q, "form": "10-Q", "start": "2026-07-01",
                     "end": "2026-09-30", "val": 29000000000, "filed": "2026-10-19"},
                    {"accn": "0001045810-25-000101", "form": "10-Q",
                     "start": "2025-07-01", "end": "2025-09-30",
                     "val": 20000000000, "filed": "2025-10-19"},
                    # Q1 year-to-date should never become the prior quarter.
                    {"accn": "0001045810-25-000100", "form": "10-Q",
                     "start": "2025-01-01", "end": "2025-09-30",
                     "val": 20000000000, "filed": "2025-10-19"}
                ]}
            }
        }}}
        rows = sec._financial_metrics(facts, ACCESSION_10Q, "10-Q")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["current"], 29000000000)
        self.assertEqual(rows[0]["previous"], 20000000000)
        self.assertEqual(rows[0]["period_end"], "2026-09-30")

    def test_no_imagined_numbers_without_matching_filing(self):
        values = {"facts": {"us-gaap": {"NetIncomeLoss": {
            "units": {"USD": [{"accn": "wrong-accession", "form": "10-K",
                              "start": "2025-01-01", "end": "2025-12-31", "val": 999}]}
        }}}}
        self.assertEqual(sec._financial_metrics(values, ACCESSION_10Q, "10-Q"), [])


if __name__ == "__main__":
    unittest.main()
