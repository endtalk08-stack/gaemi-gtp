"""Read-only: check whether the 거래대금 (trading-value) tab's data file is
actually fresh/live right now, or just an old cached snapshot -- and call
Kiwoom's industry marketcap-ranking API directly (for the real semiconductors
sector code) to see what it returns right now."""
import json
import os
import sys
import time

path = "/var/lib/gaemigtp-news/kiwoom-us-top20-news.json"
try:
    stat = os.stat(path)
    age_s = time.time() - stat.st_mtime
    print("RANKING_FILE_AGE_SECONDS", round(age_s, 1), flush=True)
    with open(path) as fh:
        data = json.load(fh)
    print("RANKING_FILE_SAMPLE", json.dumps(data)[:400], flush=True)
except Exception as exc:
    print("RANKING_FILE_ERROR", repr(exc), flush=True)

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.kiwoom_us_top20_api import _get_us_industry_map
from backend.providers.kiwoom_us_industries import _call, _access_token

try:
    sector_map = _get_us_industry_map("heatmap")
    semi = next((item for item in sector_map.get("items", [])
                 if item.get("key") == "semiconductors"), None)
    print("SEMI_ITEM", json.dumps(semi)[:400], flush=True)
    codes = (semi.get("codes") or ([semi.get("code")] if semi.get("code") else [])) if semi else []
    token = _access_token()
    for code in codes:
        try:
            body = {"stex_tp": "0", "inds_cd": str(code), "stk_tp": "1", "trde_qty_tp": "0",
                    "stk_cnd": "0", "pric_cnd": "0", "trde_prica_cnd": "0"}
            result = _call("usa20550", body, token=token)
            records = result.get("result_list")
            print("KIWOOM_USA20550", code, "n_records=",
                  len(records) if isinstance(records, list) else records,
                  "sample=", (records[:1] if isinstance(records, list) else records), flush=True)
        except Exception as exc:
            print("KIWOOM_USA20550_ERROR", code, repr(exc), flush=True)
except Exception as exc:
    print("TOP_LEVEL_ERROR", repr(exc), flush=True)
