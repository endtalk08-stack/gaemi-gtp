"""One-time read-only proof of Kiwoom REST USA index list fields.

Uses official usa10102 /api/us/stkinfo request form.
No DB changes, no service restart, no secrets, no index-price assumptions.
"""
import os
import sys
import requests

BASE = "https://api.kiwoom.com"
HEADER = {"Content-Type": "application/json;charset=UTF-8"}

def main():
    key=os.environ.get("GAEMI_KIWOOM_APP_KEY","").strip()
    secret=os.environ.get("GAEMI_KIWOOM_APP_SECRET","").strip()
    if not key or not secret:
        print("KIWOOM_INDEX_PROBE=credentials_missing",flush=True)
        return 2
    try:
        with requests.Session() as session:
            response=session.post(BASE+"/oauth2/token", json={
                "grant_type":"client_credentials","appkey":key,"secretkey":secret,
            },headers=HEADER,timeout=10,allow_redirects=False)
            if response.status_code!=200 or "application/json" not in response.headers.get("Content-Type","").lower():
                print("KIWOOM_INDEX_PROBE=oauth_http_"+str(response.status_code),flush=True)
                return 3
            token=response.json().get("token")
            if not isinstance(token,str) or not token:
                print("KIWOOM_INDEX_PROBE=oauth_rejected",flush=True)
                return 3
            print("KIWOOM_INDEX_PROBE=oauth_ok",flush=True)
            response=session.post(BASE+"/api/us/stkinfo", json={
                "index_qry_tp":"%",
            },headers={**HEADER, "api-id":"usa10102", "authorization":"Bearer "+token},
            timeout=10,allow_redirects=False)
            if response.status_code!=200 or "application/json" not in response.headers.get("Content-Type","").lower():
                print("KIWOOM_INDEX_PROBE=list_http_"+str(response.status_code),flush=True)
                return 4
            payload=response.json()
            if not isinstance(payload,dict):
                print("KIWOOM_INDEX_PROBE=list_non_object",flush=True)
                return 4
            code=payload.get("return_code")
            if code not in (None,0,"0","0000"):
                print("KIWOOM_INDEX_PROBE=list_api_rejected",flush=True)
                return 4
            data=payload.get("list")
            if not isinstance(data,list):
                print("KIWOOM_INDEX_PROBE=list_missing",flush=True)
                return 4
            print("KIWOOM_INDEX_PROBE=index_count="+str(len(data)),flush=True)
            keys=set()
            chosen=[]
            for item in data:
                if not isinstance(item,dict):
                    continue
                keys.update(item)
                name=str(item.get("index_nm") or item.get("index_enm") or "")
                if any(x in name.lower() for x in ("다우","나스닥","s&p","dow","nasdaq","s&p 500","s&p500")):
                    chosen.append((str(item.get("index_cd") or "")[:25],name[:65]))
            print("KIWOOM_INDEX_PROBE=record_keys="+",".join(sorted(keys)[:35]),flush=True)
            for code,name in chosen[:16]:
                print("KIWOOM_INDEX_NAME="+code+" "+name,flush=True)
            print("KIWOOM_INDEX_PROBE=price_fields_present="+str(any(x in keys for x in ("cur_prc","close","close_prc","flu_rt","pred_pre"))).lower(),flush=True)
            return 0
    except (requests.RequestException,ValueError,TypeError,KeyError):
        print("KIWOOM_INDEX_PROBE=transport_or_parse_failed",flush=True)
        return 5
if __name__=="__main__":
    sys.exit(main())
