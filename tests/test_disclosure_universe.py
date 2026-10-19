"""Offline-only fixed disclosure list checks: absolutely no provider calls."""
import unittest
from backend.services.disclosure_universe import (
    KR_COMPANIES, US_COMPANIES, disclosure_identity, validate_universe,
)

class TestDisclosureUniverse(unittest.TestCase):
    def test_exact_targets(self):
        self.assertTrue(validate_universe())
        self.assertEqual(len(KR_COMPANIES), 20)
        self.assertEqual(len(US_COMPANIES), 20)
        self.assertEqual(set(US_COMPANIES), {
            'NVDA','AAPL','GOOGL','MSFT','AMZN','TSM','SPCX','META','AVGO','TSLA',
            'BRK.B','LLY','SKHY','MU','WMT','JPM','AMD','V','XOM','ASML'})
    def test_alias_one_company(self):
        self.assertEqual(disclosure_identity('US','GOOG')[1], 'GOOGL')
        self.assertEqual(disclosure_identity('US','SPCX')[3], '0001181412')
        self.assertEqual(disclosure_identity('US','SKHY')[3], '0002120882')
    def test_korean_newly_included(self):
        self.assertEqual(disclosure_identity('KR','402340')[3], '01596425')
        self.assertEqual(disclosure_identity('KR','086790')[3], '00547583')
    def test_fails_closed(self):
        for market,ticker in (('US','QQQ'),('KR','035420'),('XX','NVDA'),('US','../NVDA')):
            with self.assertRaises(ValueError):
                disclosure_identity(market,ticker)

if __name__ == '__main__':
    unittest.main()
