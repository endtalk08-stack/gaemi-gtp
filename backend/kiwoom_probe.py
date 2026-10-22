"""One-shot index-code to daily-price compatibility check; no writes, orders or secrets."""
import sys
from backend.providers.kiwoom_us_quotes import (
    KiwoomReadOnlyError, credentials_configured, issue_access_token, _request,
)

MARKETS={"DJI":"다우 산업","IXIC":"나스닥 종합","INX":"S&P 500"}
DAY="20261021"

def main():
    if not credentials_configured():
        print("KIWOOM_INDEX_DAILY=credentials_missing",flush=True)
        return 2
    try:
        token=issue_access_token()
        response=_request("/api/us/stkinfo",{"index_qry_tp":"%"},{
            "authorization":"Bearer "+token, "api-id":"usa10102",
        })
        records=response.get("list")
        if not isinstance(records,list):
            print("KIWOOM_INDEX_DAILY=list_missing",flush=True)
            return 3
        mapping={str(x.get("index_cd") or ""):x for x in records if isinstance(x,dict)}
        for symbol,name in MARKETS.items():
            meta=mapping.get(symbol)
            if not meta:
                print("KIWOOM_INDEX_DAILY="+symbol+"=list_missing",flush=True)
                continue
            exchange=str(meta.get("stex_tp") or "")
            print("KIWOOM_INDEX_DAILY_META="+symbol+" exchange="+exchange[:10],flush=True)
            try:
                data=_request("/api/us/mrkcond",{
                    "stex_tp":exchange,"stk_cd":symbol,"base_dt":DAY,
                },{
                    "authorization":"Bearer "+token, "api-id":"usa20590",
                })
                items=data.get("result_list")
                if not isinstance(items,list):
                    print("KIWOOM_INDEX_DAILY="+symbol+"=no_result_list",flush=True)
                    continue
                matching=[x for x in items if isinstance(x,dict) and str(x.get("dt","")).replace("-","")==DAY]
                if not matching:
                    print("KIWOOM_INDEX_DAILY="+symbol+"=no_exact_day rows="+str(len(items)),flush=True)
                    continue
                record=matching[0]
                print("KIWOOM_INDEX_DAILY="+symbol+"=exact_day_found close="+str(record.get("cur_prc"))[:24]+" pct="+str(record.get("flu_rt"))[:24]+" symbol_echo="+str(record.get("stk_cd"))[:25],flush=True)
            except KiwoomReadOnlyError as exc:
                print("KIWOOM_INDEX_DAILY="+symbol+"=api_error_"+str(exc)[:90],flush=True)
        return 0
    except KiwoomReadOnlyError as exc:
        print("KIWOOM_INDEX_DAILY=auth_or_list_error_"+str(exc)[:90],flush=True)
        return 3
if __name__=="__main__":
    sys.exit(main())
