"""No-network unit tests for bounded one-shot disclosure collector."""
import datetime as dt
import os
import unittest
from unittest.mock import patch
from backend.services import disclosure_single_collect as c


class TestSingleCollector(unittest.TestCase):
    def test_cli_default_does_not_call_provider(self):
        with patch.object(c,"_get_json_once",side_effect=AssertionError("HTTP FORBIDDEN")):
            with patch.dict(os.environ, {"GAEMI_MANUAL_DISCLOSURE_OK":""}):
                self.assertEqual(c.main(["--market","US","--symbol","AAPL"]),0)

    def test_reject_unknown_before_connect(self):
        with self.assertRaises(ValueError):
            c.collect_once("US","QQQ")

    def test_dart_one_page_only(self):
        now=dt.datetime(2026,10,19,tzinfo=dt.timezone.utc)
        d={"status":"000","total_page":2,"list":[]}
        with patch.object(c,"_get_json_once",return_value=d) as get, patch.dict(os.environ,{"OPENDART_API_KEY":"REDACT"}):
            with self.assertRaises(c.IncompleteDisclosureWindow):
                c._collect_kr("005930","00126380",now)
            get.assert_called_once()

    def test_sec_recent_only_one_request(self):
        now=dt.datetime(2026,10,19,tzinfo=dt.timezone.utc)
        body={"cik":320193,"filings":{"recent":{
            "filingDate":["2026-10-16","2026-09-01"],
            "form":["8-K","10-Q"],
            "accessionNumber":["0000320193-26-000001","0000320193-26-000002"],
            "primaryDocument":["doc.htm","old.htm"],
            "primaryDocDescription":["8-K","10-Q"],
            "acceptanceDateTime":["2026-10-16T15:00:00","2026-09-01T12:00:00"],
        }}}
        with patch.object(c,"_get_json_once",return_value=body) as get, patch.dict(os.environ,{"SEC_USER_AGENT":"gaemi-test qa@example.com"}):
            x=c._collect_us("AAPL","0000320193",now)
            self.assertEqual(len(x),1)
            self.assertEqual(x[0]["form"],"8-K")
            get.assert_called_once()

    def test_sec_incomplete_does_not_save(self):
        now=dt.datetime(2026,10,19,tzinfo=dt.timezone.utc)
        body={"cik":320193,"filings":{"recent":{"filingDate":["2026-10-16"]}}}
        with patch.object(c,"_get_json_once",return_value=body),patch.dict(os.environ,{"SEC_USER_AGENT":"x@example.com"}):
            with self.assertRaises(c.IncompleteDisclosureWindow):
                c._collect_us("AAPL","0000320193",now)

if __name__ == "__main__":
    unittest.main()
