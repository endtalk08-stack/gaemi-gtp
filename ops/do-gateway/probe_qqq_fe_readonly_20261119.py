"""Read-only Kiwoom US FE WebSocket probe for QQQ.
Only LOGIN and REG FE for QQQ (ND); no order/account operations.
Logs only allowlisted market values; never tokens, headers or full frames.
"""
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers.kiwoom_us_quotes import issue_access_token, KiwoomReadOnlyError

WS_URI = "wss://api.kiwoom.com:10000/api/us/websocket"
SYMBOL = "QQQ"
EXCHANGE = "ND"
WATCH_SECONDS = 12

def safe_number(raw):
    try:
        value=float(str(raw).strip().replace(",",""))
        return value if -1e12 < value < 1e12 else None
    except (TypeError,ValueError):
        return None

async def read_frame(ws, seconds):
    raw=await asyncio.wait_for(ws.recv(),timeout=seconds)
    if isinstance(raw,bytes): raw=raw.decode("utf-8",errors="replace")
    try:
        value=json.loads(raw)
        return value if isinstance(value,dict) else None
    except (TypeError,ValueError):
        return None

async def probe(token):
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets.client import connect
    now=dt.datetime.now(ZoneInfo("America/New_York"))
    print("QQQ_FE_PROBE_ET="+now.isoformat(timespec="seconds"),flush=True)
    async with connect(WS_URI,open_timeout=8,close_timeout=2,ping_interval=None,max_size=131072) as ws:
        print("QQQ_FE_WS_CONNECTED=true",flush=True)
        await ws.send(json.dumps({"trnm":"LOGIN","token":token}))
        login=False
        for _ in range(5):
            frame=await read_frame(ws,7)
            if not frame: continue
            trnm=str(frame.get("trnm","")).upper()
            if trnm=="PING":
                await ws.send(json.dumps(frame)); continue
            if trnm=="LOGIN":
                login=str(frame.get("return_code","")) in ("0","0000")
                print("QQQ_FE_LOGIN_ACK="+("ok" if login else "rejected"),flush=True)
                break
            print("QQQ_FE_LOGIN_UNEXPECTED="+trnm[:15],flush=True); break
        if not login: return 4
        packet={"trnm":"REG","grp_no":"1","refresh":"1",
                "data":[{"item":[{"jmcode":SYMBOL,"stex_tp":EXCHANGE}],"type":["FE"]}]}
        await ws.send(json.dumps(packet))
        reg=False; captured=False; real=0
        deadline=asyncio.get_running_loop().time()+WATCH_SECONDS
        while asyncio.get_running_loop().time()<deadline:
            try: frame=await read_frame(ws,min(3,max(.1,deadline-asyncio.get_running_loop().time())))
            except TimeoutError: continue
            if not frame: continue
            trnm=str(frame.get("trnm","")).upper()
            if trnm=="PING":
                await ws.send(json.dumps(frame)); continue
            if trnm=="REG":
                reg=str(frame.get("return_code","")) in ("0","0000")
                print("QQQ_FE_REG_ACK="+("ok" if reg else "rejected"),flush=True)
                if not reg: return 5
            elif trnm=="REAL":
                real+=1
                for row in frame.get("data",[])[:20]:
                    if not isinstance(row,dict) or str(row.get("type","")).upper()!="FE": continue
                    if str(row.get("item","")).upper() not in ("QQQ","QQQ.ND","ND:QQQ"): continue
                    values=row.get("values")
                    if not isinstance(values,dict): continue
                    price=safe_number(values.get("10")); pct=safe_number(values.get("12"))
                    if price and price>0:
                        print("QQQ_FE_TICK="+json.dumps({"price":abs(price),"change_pct":pct},separators=(",",":")),flush=True)
                        captured=True; break
            if captured: break
        print("QQQ_FE_RESULT="+("live_tick_received" if captured else "registered_no_tick_in_window" if reg else "registration_unconfirmed"),flush=True)
        print("QQQ_FE_REAL_FRAMES="+str(real),flush=True)
        return 0 if reg else 6

def main():
    try:
        token=issue_access_token()
        print("QQQ_FE_OAUTH_OK=true",flush=True)
        return asyncio.run(probe(token))
    except KiwoomReadOnlyError as exc:
        print("QQQ_FE_PROBE_ERROR="+str(exc),flush=True)
        return 7
    except Exception as exc:
        print("QQQ_FE_PROBE_ERROR="+type(exc).__name__,flush=True)
        return 7

if __name__=="__main__":
    raise SystemExit(main())
