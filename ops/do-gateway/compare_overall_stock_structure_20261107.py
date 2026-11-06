import os, json, urllib.request, urllib.parse
from collections import Counter

key=os.environ.get("TRADINGVIEW_API_KEY","").strip()
if not key:
    raise SystemExit("MISSING_KEY")

def fetch(path, params):
    url="https://api.tradingviewapi.com"+path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={
        "Authorization":"Bearer "+key,
        "Accept":"application/json",
        "User-Agent":"gaemiGTP-feed-compare/1.0",
    })
    with urllib.request.urlopen(req,timeout=12) as r:
        payload=json.loads(r.read(3_000_000).decode("utf-8"))
    data=payload.get("data") if isinstance(payload,dict) else {}
    items=data.get("items") if isinstance(data,dict) else []
    return items if isinstance(items,list) else []

overall=fetch("/api/news",{"lang":"ko"})
stock=fetch("/api/news/stock",{"lang":"ko","market_country":"US"})

def aid(x):
    return str(x.get("id") or x.get("newsId") or "")
def title(x):
    return str(x.get("title") or "").strip()
def syms(x):
    v=x.get("relatedSymbols")
    return v if isinstance(v,list) else []

overall_with_symbols=[x for x in overall if syms(x)]
overall_without_symbols=[x for x in overall if not syms(x)]

overall_ids={aid(x) for x in overall if aid(x)}
stock_ids={aid(x) for x in stock if aid(x)}
overlap=overall_ids & stock_ids

print("OVERALL_COUNT",len(overall))
print("OVERALL_WITH_RELATED_SYMBOLS",len(overall_with_symbols))
print("OVERALL_WITHOUT_RELATED_SYMBOLS",len(overall_without_symbols))
print("STOCK_COUNT",len(stock))
print("OVERALL_STOCK_ID_OVERLAP",len(overlap))
print("OVERALL_SYMBOL_PCT","%.1f"%(100*len(overall_with_symbols)/len(overall) if overall else 0))
print("OVERALL_STOCK_OVERLAP_PCT","%.1f"%(100*len(overlap)/len(stock) if stock else 0))
print("--- OVERALL_WITH_SYMBOLS_SAMPLES ---")
for x in overall_with_symbols[:25]:
    symbols=[]
    for s in syms(x)[:4]:
        if isinstance(s,dict):
            symbols.append(str(s.get("symbol") or ""))
        else:
            symbols.append(str(s))
    print("SYMBOL_NEWS",";".join(symbols),"|",title(x)[:180])
print("--- OVERALL_WITHOUT_SYMBOLS_SAMPLES ---")
for x in overall_without_symbols[:25]:
    print("NO_SYMBOL","|",title(x)[:180])
print("--- STOCK_ONLY_SAMPLES ---")
shown=0
for x in stock:
    i=aid(x)
    if i and i not in overall_ids:
        print("STOCK_ONLY","|",title(x)[:180])
        shown+=1
        if shown>=25:
            break
print("COMPARE_COMPLETE CALLS=2")
