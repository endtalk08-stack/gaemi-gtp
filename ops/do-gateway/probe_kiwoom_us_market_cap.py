#!/usr/bin/env python3
"""One read-only Kiwoom usa20550 probe; prints sanitized market fields only."""
import json
import requests
from backend.providers.kiwoom_us_quotes import issue_access_token, KiwoomReadOnlyError

URL = "https://api.kiwoom.com/api/us/rkinfo"
BODY = {
    "stex_tp": "0",
    "inds_cd": "000",
    "stk_tp": "1",
    "trde_qty_tp": "0",
    "stk_cnd": "0",
    "pric_cnd": "0",
    "trde_prica_cnd": "0",
}
def main():
    token = issue_access_token()
    response = requests.post(
        URL, json=BODY,
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": "Bearer " + token,
            "api-id": "usa20550",
            "cont-yn": "N",
            "next-key": "",
        },
        timeout=10, allow_redirects=False,
    )
    print("KIWOOM_USA20550_HTTP=" + str(response.status_code), flush=True)
    if response.status_code != 200:
        print("KIWOOM_USA20550_PROBE=HTTP_ERROR", flush=True)
        return 2
    try:
        data = response.json()
    except ValueError:
        print("KIWOOM_USA20550_PROBE=NON_JSON", flush=True)
        return 3
    code = str(data.get("return_code", "missing"))
    print("KIWOOM_USA20550_RETURN_CODE=" + code, flush=True)
    if code not in ("0", "0000"):
        print("KIWOOM_USA20550_PROBE=API_REJECTED", flush=True)
        return 4
    rows = data.get("result_list")
    if not isinstance(rows, list):
        print("KIWOOM_USA20550_PROBE=RESULT_LIST_MISSING", flush=True)
        return 5
    safe = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        safe.append({
            "rank": row.get("rank"),
            "symbol": row.get("stk_cd"),
            "name": row.get("stk_nm") or row.get("stk_enm"),
            "exchange": row.get("stex_tp"),
            "market_cap_thousand_usd": row.get("mac"),
            "market_cap_weight": row.get("mac_wght"),
            "price": row.get("cur_prc"),
            "change_pct": row.get("flu_rt"),
            "volume": row.get("acc_trde_qty"),
        })
    print("KIWOOM_USA20550_RESULT_COUNT=" + str(len(rows)), flush=True)
    print("KIWOOM_USA20550_SAMPLE=" + json.dumps(safe, ensure_ascii=False), flush=True)
    print("KIWOOM_USA20550_PROBE=PASS", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
