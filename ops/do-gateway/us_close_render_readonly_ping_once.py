"""Probe live Render US-close GET from existing DO, read-only and no secrets."""
import json
import re
import sys
import urllib.error
import urllib.request

URL="https://gaemi-gtp.onrender.com/api/market/us-close"
def main():
    print("RENDER_US_CLOSE_PROBE=GET_api_market_us-close",flush=True)
    req=urllib.request.Request(URL,headers={
        "Accept":"application/json","User-Agent":"gaemiGTP-deployment-verify/1.0"},method="GET")
    try:
        with urllib.request.urlopen(req,timeout=18) as resp:
            status=resp.status
            typ=resp.headers.get("Content-Type")
            payload=resp.read(14000)
    except urllib.error.HTTPError as exc:
        print("RENDER_US_CLOSE_HTTP="+str(exc.code),flush=True)
        return 2
    except Exception as exc:
        print("RENDER_US_CLOSE_ERROR="+type(exc).__name__,flush=True)
        return 3
    print("RENDER_US_CLOSE_HTTP="+str(status),flush=True)
    if status!=200 or "json" not in str(typ).lower():return 4
    try:data=json.loads(payload)
    except (TypeError,ValueError):return 5
    body=str(data.get("content") or "")
    print("RENDER_US_CLOSE_FIELDS="+json.dumps({
        "ok":data.get("ok"),"available":data.get("available"),
        "session_date":data.get("session_date"),"content_chars":len(body),
        "contains_date":("2026-10-19" in body),
        "contains_dow":("51,966.03" in body),
        "contains_nasdaq":("26,430.89" in body),
        "contains_sp500":("7,690.73" in body),
        "hashtags":len(re.findall(r"#[^\s#]+",body)),
        "preview":body[:950]
    },ensure_ascii=False),flush=True)
    if not (data.get("ok") and data.get("available") and
        data.get("session_date")=="2026-10-19" and
        all(x in body for x in ("51,966.03","26,430.89","7,690.73"))):
        return 6
    print("RENDER_US_CLOSE_LIVE_PASS",flush=True)
    return 0
if __name__=="__main__":sys.exit(main())
