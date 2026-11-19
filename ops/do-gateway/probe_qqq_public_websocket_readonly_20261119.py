"""Public-path verification: existing TOP20 HTTPS plus the new QQQ WebSocket."""
import asyncio, json, urllib.request

TOP20_URL="http://127.0.0.1:8765/market/trading-value?market=us"
WS_URL="wss://quotes.gaemigtp.com/ws/us-live-quotes"
ORIGIN="https://40e589a3.gaemigtp-main.pages.dev"

def check_top20():
    with urllib.request.urlopen(TOP20_URL, timeout=10) as response:
        data=json.loads(response.read().decode("utf-8"))
    items=data.get("items")
    if response.status != 200 or data.get("ok") is not True or not isinstance(items,list) or len(items)!=20:
        raise RuntimeError("existing_top20_endpoint_failed")
    print("QQQ_TEST_TOP20_LOCAL=ok count=20",flush=True)

async def check_ws():
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets.client import connect
    async with connect(
        WS_URL, origin=ORIGIN, open_timeout=10, close_timeout=2,
        ping_interval=None, max_size=16384,
    ) as ws:
        print("QQQ_TEST_PUBLIC_WS=connected",flush=True)
        deadline=asyncio.get_running_loop().time()+30
        saw_message=False
        while asyncio.get_running_loop().time()<deadline:
            try:
                raw=await asyncio.wait_for(ws.recv(),timeout=12)
            except asyncio.TimeoutError:
                continue
            frame=json.loads(raw)
            if not isinstance(frame,dict) or frame.get("type")!="quote":
                continue
            saw_message=True
            quote=frame.get("quote")
            if quote is None:
                print("QQQ_TEST_PUBLIC_WS=connected_quote_waiting",flush=True)
                continue
            if (quote.get("symbol")!="QQQ" or
                not isinstance(quote.get("price"),(int,float)) or quote["price"]<=0 or
                not isinstance(quote.get("received_at_ms"),int)):
                raise RuntimeError("qqq_quote_schema_invalid")
            print("QQQ_TEST_LIVE_TICK="+json.dumps({
                "symbol":quote["symbol"],"price":quote["price"],
                "change_pct":quote.get("change_pct"),"stale":quote.get("stale")
            },separators=(",",":")),flush=True)
            return 0
        if saw_message:
            print("QQQ_TEST_RESULT=websocket_ok_no_tick_in_30s",flush=True)
            return 0
        raise RuntimeError("qqq_websocket_no_message")

def main():
    check_top20()
    return asyncio.run(check_ws())

if __name__=="__main__":
    raise SystemExit(main())
