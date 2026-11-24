"""Read-only existing market-cap ranks attached to current live heatmap. No Kiwoom request."""
import json,ssl,urllib.request
u="https://127.0.0.1/market/us-industries?include_stocks=1&view=heatmap"
req=urllib.request.Request(u,headers={"Host":"quotes.gaemigtp.com","Origin":"https://gaemigtp-main.pages.dev"})
with urllib.request.urlopen(req,context=ssl._create_unverified_context(),timeout=55) as response:
    data=json.load(response)
for row in data.get("items",[]):
    o={"key":row.get("key"),"name":row.get("name"),"group_source":row.get("source"),"members":[]}
    for stock in row.get("stocks",[]):
        if isinstance(stock,dict):
            o["members"].append({k:stock.get(k) for k in ("symbol","rank","source_rank","market_cap_usd","issuer_key","exchange")})
    print("SECTOR_EXISTING_RANKS="+json.dumps(o,ensure_ascii=False,separators=(",",":")),flush=True)
