"""Read-only live Pages chart response check. No secrets or service mutation."""
import json
import requests

for base in ("https://gaemigtp-main.pages.dev","https://gaemigtp.com"):
    for symbol in ("NVDA","CRWV"):
        try:
            r=requests.get(base+"/market/us-daily-chart",params={"symbol":symbol},
                           timeout=10,headers={"Accept":"application/json","Cache-Control":"no-cache"})
            try:
                d=r.json()
                rows=d.get("rows") or []
                last=rows[-1].get("date") if rows else None
                okay=d.get("ok")
            except ValueError:
                okay=False; last=None
            print("CHART_PAGES_VERIFY host=%s symbol=%s http=%s ok=%s last=%s" %
                  (base.split("//",1)[1],symbol,r.status_code,okay,last),flush=True)
        except requests.RequestException as e:
            print("CHART_PAGES_VERIFY host=%s symbol=%s error=%s" %
                  (base.split("//",1)[1],symbol,type(e).__name__),flush=True)
