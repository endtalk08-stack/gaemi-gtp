"""One-shot QQQ FE check using the existing systemd Kiwoom credential files.
No account/order API; only OAuth and one 12-second QQQ FE subscription.
Credential values and raw frames are never printed.
"""
import asyncio
import datetime as dt
import json
import subprocess
import sys
from zoneinfo import ZoneInfo

def child():
    import os
    sys.path.insert(0, "/opt/gaemigtp-news/app")
    from backend.providers.kiwoom_us_quotes import issue_access_token
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets.client import connect

    async def run():
        token = issue_access_token()
        print("QQQ_OAUTH=ok", flush=True)
        uri = "wss://api.kiwoom.com:10000/api/us/websocket"
        async with connect(uri, open_timeout=8, close_timeout=2,
                           ping_interval=None, max_size=131072) as ws:
            await ws.send(json.dumps({"trnm":"LOGIN","token":token}))
            login_ok = False
            for _ in range(5):
                raw = await asyncio.wait_for(ws.recv(), timeout=7)
                frame = json.loads(raw)
                trnm = str(frame.get("trnm","")).upper()
                if trnm == "PING":
                    await ws.send(json.dumps(frame))
                elif trnm == "LOGIN":
                    login_ok = str(frame.get("return_code","")) in ("0","0000")
                    print("QQQ_LOGIN=" + ("ok" if login_ok else "rejected"), flush=True)
                    break
            if not login_ok:
                return 11
            await ws.send(json.dumps({"trnm":"REG","grp_no":"1","refresh":"1",
                "data":[{"item":[{"jmcode":"QQQ","stex_tp":"ND"}],"type":["FE"]}]}))
            registered = False
            tick = False
            deadline = asyncio.get_running_loop().time() + 12
            while asyncio.get_running_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3)
                except asyncio.TimeoutError:
                    continue
                frame = json.loads(raw)
                trnm = str(frame.get("trnm","")).upper()
                if trnm == "PING":
                    await ws.send(json.dumps(frame))
                elif trnm == "REG":
                    registered = str(frame.get("return_code","")) in ("0","0000")
                    print("QQQ_REG=" + ("ok" if registered else "rejected"), flush=True)
                    if not registered:
                        return 12
                elif trnm == "REAL":
                    for row in frame.get("data",[])[:20]:
                        if not isinstance(row,dict) or str(row.get("type","")).upper()!="FE":
                            continue
                        item=str(row.get("item","")).upper()
                        if item not in ("QQQ","QQQ.ND","ND:QQQ"):
                            continue
                        values=row.get("values")
                        if not isinstance(values,dict):
                            continue
                        try:
                            price=abs(float(str(values.get("10","")).replace(",","")))
                            change=float(str(values.get("12","")).replace(",",""))
                        except (TypeError,ValueError):
                            continue
                        if 0 < price < 10000000:
                            print("QQQ_TICK="+json.dumps({"price":price,"change_pct":change}),flush=True)
                            tick=True
                            break
                if tick:
                    break
            print("QQQ_PROBE_RESULT="+("live_tick_received" if tick else "registered_no_tick_in_12s" if registered else "registration_unconfirmed"),flush=True)
            return 0 if registered else 13
    try:
        now=dt.datetime.now(ZoneInfo("America/New_York"))
        print("QQQ_PROBE_ET="+now.isoformat(timespec="seconds"),flush=True)
        return asyncio.run(run())
    except Exception as exc:
        print("QQQ_PROBE_ERROR="+type(exc).__name__,flush=True)
        return 14

def main():
    if len(sys.argv)>1 and sys.argv[1]=="--child":
        raise SystemExit(child())
    command=[
        "systemd-run","--unit=gaemi-qqq-fe-probe-20261119","--wait","--pipe","--collect",
        "--property=User=gaemigtp-news","--property=Group=gaemigtp-news",
        "--property=WorkingDirectory=/opt/gaemigtp-news/app",
        "--property=EnvironmentFile=/etc/gaemigtp/kiwoom.env",
        "--property=EnvironmentFile=/etc/gaemigtp/news-worker.env",
        "--property=TimeoutStartSec=40s",
        "/opt/gaemigtp-news/venv/bin/python","/run/gaemi-gateway/payload","--child"
    ]
    try:
        p=subprocess.run(command,capture_output=True,text=True,timeout=50)
        output=(p.stdout or "")+(p.stderr or "")
        for line in output.splitlines():
            if line.startswith(("QQQ_","Running as unit")):
                print(line[:300],flush=True)
        print("QQQ_SYSTEMD_PROBE_EXIT="+str(p.returncode),flush=True)
        return p.returncode
    except Exception as exc:
        print("QQQ_SYSTEMD_PROBE_ERROR="+type(exc).__name__,flush=True)
        return 15

if __name__=="__main__":
    main()
