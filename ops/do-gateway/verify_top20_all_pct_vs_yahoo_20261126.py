import concurrent.futures, datetime as dt, json, pathlib, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
data=json.loads(pathlib.Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json").read_text(encoding="utf-8"))
captured=dt.datetime.fromisoformat(data["captured_at"].replace("Z","+00:00"))
day=captured.astimezone(ZoneInfo("America/New_York")).date()
def check(row):
    symbol=row["symbol"]; yahoo={"BRKB":"BRK-B","BRKA":"BRK-A"}.get(symbol,symbol.replace(".","-"))
    url="https://query1.finance.yahoo.com/v8/finance/chart/"+urllib.parse.quote(yahoo,safe="")+"?range=10d&interval=1d"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=10) as response: payload=json.load(response)
        result=payload["chart"]["result"][0]; ts=result["timestamp"]; closes=result["indicators"]["quote"][0]["close"]
        vals=[]
        for stamp,close in zip(ts,closes):
            if type(close) in (int,float):
                d=dt.datetime.fromtimestamp(stamp,ZoneInfo("America/New_York")).date()
                if d<=day: vals.append((d,float(close)))
        prev=next((v for d,v in reversed(vals) if d<day),None)
        curr=next((v for d,v in reversed(vals) if d==day),None)
        calc=(curr/prev-1)*100 if curr and prev else None
        pct=row.get("change_pct")
        ok=(calc is not None and type(pct) in (int,float) and abs(calc-pct)<=0.15
            and abs(curr-row.get("price",0))<=max(0.02,curr*0.0002))
        return (symbol,ok,pct,calc,curr,row.get("price"))
    except Exception as exc:
        return (symbol,False,"error",type(exc).__name__,None,None)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    results=list(pool.map(check,data.get("items") or []))
passed=[r for r in results if r[1]]
failed=[r for r in results if not r[1]]
print("CAPTURE_DAY="+day.isoformat(),flush=True)
print("MATCHED=%d/%d" % (len(passed),len(results)),flush=True)
for row in failed: print("MISMATCH="+repr(row),flush=True)
