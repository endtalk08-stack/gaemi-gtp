"""US stock trading-value Top 20 from Kiwoom REST usa20540 only.

Read-only public market TR; never access account/order paths.
Do not interpret absent field values, signed Kiwoom prices, or exchange codes.
"""
import math
import re

import requests

from backend.providers.kiwoom_us_quotes import issue_access_token, KiwoomReadOnlyError

US_RANKING_PATH = "https://api.kiwoom.com/api/us/rkinfo"
RANKING_ID = "usa20540"
RANKING_REQUEST = {
    "stex_tp": "0", "inds_cd": "000", "stk_tp": "1",
    "trde_qty_tp": "0", "stk_cnd": "0",
    "pric_cnd": "0", "trde_prica_cnd": "0",
}
# Response result_list includes these fields per official Kiwoom usa20540.
FIELDS = ("rank", "stex_tp", "stk_cd", "stk_nm", "stk_enm",
          "cur_prc", "pred_pre_sig", "pred_pre", "flu_rt",
          "acc_trde_qty", "pred_trde_qty", "trde_prica")
EXCHANGES = {"ND", "NY", "NA"}
EXCHANGE_CODES = {"1": "NY", "2": "ND", "3": "NA"}

def _num(raw):
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(str(raw).strip().replace(",", "").replace("+", "").replace("%", ""))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None

def _nonnegative(raw):
    value = _num(raw)
    return value if value is not None and value >= 0 else None

def _normalize_row(record, position):
    if isinstance(record, (list, tuple)):
        record = dict(zip(FIELDS, record))
    if not isinstance(record, dict):
        return None
    code = str(record.get("stk_cd") or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9.\\-]{1,20}", code):
        return None
    exchange_code = str(record.get("stex_tp") or "").strip().upper()
    exchange = EXCHANGE_CODES.get(exchange_code, exchange_code)
    if exchange not in EXCHANGES:
        return None
    # Prefer official Korean display name, fall back to English.
    name = str(record.get("stk_nm") or record.get("stk_enm") or "").strip()
    if not name or len(name) > 80:
        return None
    try:
        rank = int(str(record.get("rank") or position).strip())
    except (TypeError, ValueError):
        rank = position
    price = _num(record.get("cur_prc"))
    return {
        "rank": rank if rank > 0 else position,
        "symbol": code,
        "name": name,
        "english_name": str(record.get("stk_enm") or "").strip()[:80],
        "exchange": exchange,
        "price": abs(price) if price not in (None, 0) else None,
        "change_pct": _num(record.get("flu_rt")),
        "trading_value": _nonnegative(record.get("trde_prica")),
        "volume": _nonnegative(record.get("acc_trde_qty")),
        "industry": None,
        "source": "kiwoom",
    }

def fetch_us_trading_value_top(limit=20, *, token=None):
    """One source-ranked page of USA stocks; no per-ticker calls."""
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("invalid_rank_limit")
    access_token = token or issue_access_token()
    try:
        response = requests.post(
            US_RANKING_PATH, json=RANKING_REQUEST,
            headers={"Content-Type": "application/json;charset=UTF-8",
                     "authorization": "Bearer " + access_token,
                     "api-id": RANKING_ID},
            timeout=10, allow_redirects=False,
        )
        if response.status_code != 200:
            raise KiwoomReadOnlyError("kiwoom_rank_http_" + str(response.status_code))
        data = response.json()
    except (requests.RequestException, ValueError):
        raise KiwoomReadOnlyError("kiwoom_rank_transport_error") from None
    if not isinstance(data, dict):
        raise KiwoomReadOnlyError("kiwoom_rank_response_invalid")
    code = str(data.get("return_code", 0))
    if code not in ("0", "0000"):
        safe = code if re.fullmatch(r"-?[0-9]{1,6}", code) else "unknown"
        raise KiwoomReadOnlyError("kiwoom_rank_rejected_code_" + safe)
    records = data.get("result_list")
    if not isinstance(records, list):
        raise KiwoomReadOnlyError("kiwoom_rank_records_missing")
    rows = []
    seen = set()
    for record in records:
        row = _normalize_row(record, len(rows) + 1)
        if row and row["symbol"] not in seen:
            seen.add(row["symbol"])
            rows.append(row)
        if len(rows) >= limit:
            break
    if not rows:
        raise KiwoomReadOnlyError("kiwoom_rank_records_empty")
    # Maintain original provider sort, never reorder by nullable/truncated price.
    for index, row in enumerate(rows):
        row["rank"] = index + 1
    return rows
