"""One-time inspection of official Kiwoom US index list; never calls trading."""
import sys
from backend.providers.kiwoom_us_quotes import (
    KiwoomReadOnlyError, credentials_configured, issue_access_token, _request,
)

def main():
    if not credentials_configured():
        print("KIWOOM_INDEX_LIST=credentials_missing",flush=True)
        return 2
    try:
        token=issue_access_token()
        print("KIWOOM_INDEX_LIST=oauth_ok",flush=True)
        payload=_request("/api/us/stkinfo", {"index_qry_tp":"%"}, {
            "authorization":"Bearer "+token, "api-id":"usa10102",
        })
        records=payload.get("list")
        if not isinstance(records,list):
            print("KIWOOM_INDEX_LIST=list_missing",flush=True)
            return 3
        keys=set()
        names=[]
        for item in records:
            if not isinstance(item,dict):continue
            keys.update(item)
            name=str(item.get("index_nm") or item.get("index_enm") or "")
            if any(t in name.lower() for t in ("다우","나스닥","s&p","dow","nasdaq","s&p500")):
                names.append((str(item.get("index_cd") or "")[:24],name[:60]))
        print("KIWOOM_INDEX_LIST=count="+str(len(records)),flush=True)
        print("KIWOOM_INDEX_LIST=keys="+",".join(sorted(keys)[:35]),flush=True)
        print("KIWOOM_INDEX_LIST=has_price_or_pct="+str(any(k in keys for k in ("cur_prc","close","close_prc","flu_rt","pred_pre"))).lower(),flush=True)
        for code,name in names[:14]:
            print("KIWOOM_INDEX_LIST=matched_code="+code+" name="+name,flush=True)
        return 0
    except KiwoomReadOnlyError as exc:
        print("KIWOOM_INDEX_LIST=api_error_"+str(exc)[:90],flush=True)
        return 4
if __name__=="__main__":
    sys.exit(main())
