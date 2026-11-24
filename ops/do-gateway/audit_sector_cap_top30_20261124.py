"""One-time read-only verification of displayed US industry stocks against Kiwoom market-cap rankings.
No changes to live quote service or subscriptions. Output only public ticker/cap/ranks.
"""
import json, ssl, sys, urllib.request, traceback
sys.path.insert(0, "/opt/gaemigtp-news/app")

def main():
    from backend.providers.kiwoom_us_industries import fetch_us_industry_stocks
    url="https://127.0.0.1/market/us-industries?include_stocks=1&view=heatmap"
    req=urllib.request.Request(url,headers={"Host":"quotes.gaemigtp.com","Origin":"https://gaemigtp-main.pages.dev"})
    with urllib.request.urlopen(req,context=ssl._create_unverified_context(),timeout=55) as response:
        rows=json.load(response).get("items",[])
    for group in rows:
        key=group.get("key","")
        shown=[str(x.get("symbol","")).upper() for x in group.get("stocks",[]) if isinstance(x,dict)]
        codes=group.get("codes") or ([group.get("code")] if group.get("code") else [])
        result={"key":key,"name":group.get("name"),"shown":shown,"codes":codes}
        if key=="bitcoin_related":
            result["note"]="theme_not_official_industry_ranking"
        elif key=="internet_platforms":
            result["note"]="custom_group; individual member official industry may differ"
        if codes:
            try:
                ranking=fetch_us_industry_stocks(codes,"marketcap",limit=36)
                ranked=ranking.get("items",[])
                bysymbol={str(x.get("symbol","")).upper().split(".")[0]:x for x in ranked}
                result["returned_count"]=len(ranked)
                result["matches"]=[]
                for s in shown:
                    x=bysymbol.get(s.split(".")[0])
                    result["matches"].append({"symbol":s,"position_in_returned":x.get("rank") if x else None,"market_cap_usd":x.get("market_cap_usd") if x else None,"status":("within_30_of_returned" if x and x.get("rank",999)<=30 else "after_30_in_returned" if x else "not_in_returned_ranking")})
                result["top35"]=[x.get("symbol") for x in ranked[:35]]
            except Exception as e:
                result["error"]=type(e).__name__+":"+str(e)[:85]
        print("SECTOR_CAP_AUDIT="+json.dumps(result,ensure_ascii=False,separators=(",",":")),flush=True)

if __name__=="__main__":
    main()
