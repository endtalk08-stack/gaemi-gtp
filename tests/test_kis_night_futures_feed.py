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
