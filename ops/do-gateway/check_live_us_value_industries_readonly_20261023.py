"""Verify authenticated Render US trading-value response has every sector.
Read-only, no tokens or credentials in logs, no DB writes.
"""
import os
import requests

token=os.environ.get("NEWS_WORKER_RANKING_TOKEN","").strip()
if len(token)<32:
    print("US_VALUE_INDUSTRY_LIVE=no_worker_read_token",flush=True)
    raise SystemExit(2)
try:
    r=requests.get(
        "https://gaemi-gtp.onrender.com/market/trading-value?market=us",
        headers={"X-Gaemi-News-Worker-Token":token},
        timeout=16,allow_redirects=False)
    doc=r.json() if r.headers.get("Content-Type","").startswith("application/json") else {}
except (requests.RequestException,ValueError) as exc:
    print("US_VALUE_INDUSTRY_LIVE_ERROR="+type(exc).__name__,flush=True)
    raise SystemExit(3)
items=doc.get("items") if isinstance(doc,dict) else None
items=items if isinstance(items,list) else []
filled=sum(1 for item in items if isinstance(item,dict) and isinstance(item.get("industry"),str) and item["industry"].strip())
print("US_VALUE_INDUSTRY_LIVE="+repr({"http":r.status_code,"source":doc.get("source"),
      "items":len(items),"industries":filled,
      "first3":[(x.get("symbol"),x.get("industry")) for x in items[:3]]}),flush=True)
if r.status_code!=200 or doc.get("source")!="kiwoom" or len(items)!=20 or filled!=20:
    raise SystemExit(4)
print("US_VALUE_INDUSTRY_LIVE_PASS",flush=True)
