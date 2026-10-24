"""Read-only Render sidebar check with existing private worker token.
Log only status, source, row counts and bounded error identifiers. Never token.
"""
import os
import requests

base="https://gaemi-gtp.onrender.com"
token=os.environ.get("NEWS_WORKER_RANKING_TOKEN","").strip()
print("DIAG_RANK_TOKEN_PRESENT=" + str(bool(token)).lower(),flush=True)
for path in ("/health","/market/trading-value?market=us"):
    try:
        headers={"X-Gaemi-News-Worker-Token":token} if token else {}
        res=requests.get(base+path,headers=headers,timeout=22,allow_redirects=False)
        print("DIAG_PATH="+path.split("?")[0]+" STATUS="+str(res.status_code)+
              " CONTENT_TYPE="+res.headers.get("Content-Type","").split(";")[0],flush=True)
        try:
            data=res.json()
            if isinstance(data,dict):
                items=data.get("items")
                print("DIAG_RESPONSE="+str({"ok":data.get("ok"),
                    "source":data.get("source"),"error":data.get("error"),
                    "provider_status":data.get("provider_status"),
                    "backend_marker":res.headers.get("X-Gaemi-US-Value-Provider"),
                    "rows":len(items) if isinstance(items,list) else None,
                    "first_symbol":items[0].get("symbol") if isinstance(items,list) and items else None}),flush=True)
        except ValueError:
            print("DIAG_JSON=no",flush=True)
    except requests.RequestException as exc:
        print("DIAG_REQUEST_EXCEPTION="+type(exc).__name__,flush=True)


# Read-only: verify Kiwoom's *actual* closed-session OHLC is still obtainable.
# Do not mutate Neon, create tables, or substitute another provider.
try:
    from backend.providers.kiwoom_us_quotes import fetch_us_quote
    quote=fetch_us_quote("MU", "ND")
    high=quote.get("high")
    low=quote.get("low")
    print("DIAG_KIWOOM_USA20100_HIGH_LOW=" +
          str({"symbol":"MU", "high":high, "low":low,
               "valid":bool(high and low and high >= low > 0)}),flush=True)
except Exception as exc:
    print("DIAG_KIWOOM_USA20100_ERROR=" + type(exc).__name__ +
          ":" + str(exc)[:110],flush=True)
