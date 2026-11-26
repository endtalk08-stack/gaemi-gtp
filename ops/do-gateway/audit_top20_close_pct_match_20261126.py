import datetime as dt, json, pathlib, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
p=pathlib.Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
data=json.loads(p.read_text(encoding="utf-8"))
captured=dt.datetime.fromisoformat(data["captured_at"].replace("Z","+00:00"))
day=captured.astimezone(ZoneInfo("America/New_York")).date()
print("CAPTURED_SESSION_DAY="+day.isoformat(),flush=True)
for row in (data.get("items") or [])[:5]:
    symbol=row["symbol"]
    yahoo={"BRKB":"BRK-B","BRKA":"BRK-A"}.get(symbol,symbol.replace(".","-"))
    url="https://query1.finance.yahoo.com/v8/finance/chart/"+urllib.parse.quote(yahoo,safe="")+"?range=10d&interval=1d"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=8) as response: payload=json.load(response)
        result=payload["chart"]["result"][0]
        ts=result["timestamp"]; closes=result["indicators"]["quote"][0]["close"]
        vals=[]
        for stamp,close in zip(ts,closes):
            if type(close) in (int,float):
                d=dt.datetime.fromtimestamp(stamp,ZoneInfo("America/New_York")).date()
                if d<=day: vals.append((d,float(close)))
        vals.sort()
        prev=next((v for d,v in reversed(vals) if d<day),None)
        curr=next((v for d,v in reversed(vals) if d==day),None)
        calc=(curr/prev-1)*100 if curr and prev else None
        print("SYMBOL=%s row_price=%s row_pct=%s yahoo_close=%s yahoo_prev=%s calc_pct=%s" %
              (symbol,row.get("price"),row.get("change_pct"),curr,prev,calc),flush=True)
    except Exception as exc:
        print("SYMBOL=%s yahoo_error=%s" % (symbol,type(exc).__name__),flush=True)
