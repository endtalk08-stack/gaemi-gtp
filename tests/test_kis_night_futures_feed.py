import unittest.mock
import base64
import unittest

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from backend.kis_night_futures_feed import (
    DEFAULT_SYMBOL,
    QUOTE_FIELDS,
    TRADE_FIELDS,
    QUOTE_TR_ID,
    TRADES_TR_ID,
    decode_realtime_frame,
)


def make_frame(tr_id, fields, values):
    row = [""] * len(fields)
    for name, value in values.items():
        row[fields.index(name)] = str(value)
    return "0|{}|{}|{}".format(tr_id, DEFAULT_SYMBOL, "^".join(row))


class KISNightFuturesFrameTests(unittest.TestCase):
    def test_trade_frame_extracts_price_and_daily_change(self):
        frame = make_frame(TRADES_TR_ID, TRADE_FIELDS, {
            "futs_shrn_iscd": DEFAULT_SYMBOL,
            "bsop_hour": "213045",
            "futs_prpr": "352.75",
            "futs_prdy_ctrt": "0.42",
            "last_cnqn": "3",
            "acml_vol": "128",
        })
        quote = decode_realtime_frame(frame)
        self.assertEqual(quote["price"], 352.75)
        self.assertEqual(quote["change_pct"], 0.42)
        self.assertEqual(quote["last_volume"], 3)
        self.assertEqual(quote["accumulated_volume"], 128)
        self.assertEqual(quote["symbol"], DEFAULT_SYMBOL)

    def test_encrypted_trade_frame_uses_the_kis_subscription_key_and_iv(self):
        values = [""] * len(TRADE_FIELDS)
        values[TRADE_FIELDS.index("futs_shrn_iscd")] = DEFAULT_SYMBOL
        values[TRADE_FIELDS.index("bsop_hour")] = "213047"
        values[TRADE_FIELDS.index("futs_prpr")] = "353.10"
        values[TRADE_FIELDS.index("futs_prdy_ctrt")] = "0.51"
        plain = "^".join(values).encode("utf-8")
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded = padder.update(plain) + padder.finalize()
        key, iv = "0123456789abcdef", "abcdef0123456789"
        encryptor = Cipher(algorithms.AES(key.encode()), modes.CBC(iv.encode())).encryptor()
        encrypted = base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode()
        frame = "1|{}|{}|{}".format(TRADES_TR_ID, DEFAULT_SYMBOL, encrypted)
        quote = decode_realtime_frame(frame, encryption={"key": key, "iv": iv})
        self.assertEqual(quote["price"], 353.10)
        self.assertEqual(quote["change_pct"], 0.51)
        self.assertIsNone(decode_realtime_frame(frame))

    def test_order_book_frame_extracts_best_bid_ask_and_sizes(self):
        frame = make_frame(QUOTE_TR_ID, QUOTE_FIELDS, {
            "futs_shrn_iscd": DEFAULT_SYMBOL,
            "bsop_hour": "213046",
            "futs_askp1": "352.80",
            "futs_bidp1": "352.75",
            "askp_rsqn1": "12",
            "bidp_rsqn1": "9",
        })
        quote = decode_realtime_frame(frame)
        self.assertEqual(quote["best_ask"], 352.8)
        self.assertEqual(quote["best_bid"], 352.75)
        self.assertEqual(quote["ask_quantity"], 12)
        self.assertEqual(quote["bid_quantity"], 9)

    def test_rejects_unexpected_symbol_and_invalid_trade_price(self):
        wrong_symbol = "0|{}|999W0000|{}".format(
            TRADES_TR_ID, "^".join([""] * len(TRADE_FIELDS))
        )
        self.assertIsNone(decode_realtime_frame(wrong_symbol))
        invalid = make_frame(TRADES_TR_ID, TRADE_FIELDS, {
            "futs_shrn_iscd": DEFAULT_SYMBOL,
            "futs_prpr": "0",
            "futs_prdy_ctrt": "0.1",
        })
        self.assertIsNone(decode_realtime_frame(invalid))


if __name__ == "__main__":
    unittest.main()


import datetime as _dt
import io as _io
import json as _json
import tempfile as _tempfile
from pathlib import Path as _Path

import backend.kis_night_futures_feed as _feed


class _Response(_io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FrontMonthAndClosingPriceTests(unittest.TestCase):
    def test_front_month_rolls_on_the_second_thursday(self):
        f = _feed.front_month_code
        self.assertEqual(f(_dt.date(2026, 11, 28)), "A01612")
        self.assertEqual(f(_dt.date(2026, 12, 9)), "A01612")
        self.assertEqual(f(_dt.date(2026, 12, 10)), "A01703")   # expiry day: night session trades March
        self.assertEqual(f(_dt.date(2027, 3, 11)), "A01706")

    def test_last_price_prefers_the_night_session_then_the_day_session(self):
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            if "FID_COND_MRKT_DIV_CODE=CM" in request.full_url:
                return _Response(_json.dumps({"output1": {"futs_prpr": "760.05", "futs_prdy_ctrt": "0.38"}}).encode())
            return _Response(b"{}")
        quote = _feed.fetch_last_price("k", "s", "A01612", opener=opener, token="t")
        self.assertEqual(quote, {"symbol": "A01612", "price": 760.05, "change_pct": 0.38, "source": "kis:rest-night"})
        self.assertEqual(len(calls), 1)

    def test_day_session_price_when_the_night_session_has_none(self):
        def opener(request, timeout):
            if "FID_COND_MRKT_DIV_CODE=F" in request.full_url:
                return _Response(_json.dumps({"output1": {"futs_prpr": "757.15", "futs_prdy_ctrt": "4.18"}}).encode())
            return _Response(_json.dumps({"output1": {"futs_prpr": ""}}).encode())
        with unittest.mock.patch.object(_feed.time, "sleep"):
            quote = _feed.fetch_last_price("k", "s", "A01612", opener=opener, token="t")
        self.assertEqual((quote["price"], quote["source"]), (757.15, "kis:rest-day"))

    def test_last_quote_survives_a_restart(self):
        path = _Path(_tempfile.mkdtemp()) / "last.json"
        self.assertIsNone(_feed.load_last_quote(path))
        _feed.save_last_quote({"symbol": "A01612", "price": 760.05, "change_pct": 0.38, "secret": "x"}, path)
        self.assertEqual(_feed.load_last_quote(path)["price"], 760.05)
        self.assertNotIn("secret", _feed.load_last_quote(path))

    def test_access_token_is_reused_until_it_expires(self):
        path = _Path(_tempfile.mkdtemp()) / "token.json"
        issued = []

        def opener(request, timeout):
            issued.append(1)
            return _Response(_json.dumps({"access_token": "tok", "expires_in": 86400}).encode())
        self.assertEqual(_feed.get_access_token("k", "s", path=path, now=1000, opener=opener), "tok")
        self.assertEqual(_feed.get_access_token("k", "s", path=path, now=2000, opener=opener), "tok")
        self.assertEqual(len(issued), 1)
