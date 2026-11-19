"""One-time read-only end-to-end QQQ WebSocket check through the public origin."""
import asyncio, json, ssl, time
from urllib.parse import urlparse

async def main():
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets import connect
    url="wss://quotes.gaemigtp.com/ws/us-live-quotes"
    origin="https://40e589a3.gaemigtp-main.pages.dev"
    started=time.monotonic()
    try:
        async with connect(
            url, origin=origin, open_timeout=8, close_timeout=2,
            ping_interval=15, max_size=65536,
        ) as ws:
            print("QQQ_WS_HANDSHAKE=PASS",flush=True)
            try:
                raw=await asyncio.wait_for(ws.recv(),timeout=8)
                data=json.loads(raw)
                quote=data.get("quote") if isinstance(data,dict) else None
                print("QQQ_WS_FRAME_TYPE="+str(data.get("type") if isinstance(data,dict) else "invalid"),flush=True)
                if isinstance(quote,dict):
                    print("QQQ_WS_SYMBOL="+str(quote.get("symbol")),flush=True)
                    print("QQQ_WS_PRICE_PRESENT="+str(type(quote.get("price")) in (int,float)).lower(),flush=True)
                    print("QQQ_WS_STALE="+str(bool(quote.get("stale"))).lower(),flush=True)
                    print("QQQ_WS_RECEIVED_AT_PRESENT="+str(type(quote.get("received_at_ms")) is int).lower(),flush=True)
                else:
                    print("QQQ_WS_QUOTE_NULL=true",flush=True)
            except asyncio.TimeoutError:
                print("QQQ_WS_FRAME_TIMEOUT=true",flush=True)
    except Exception as exc:
        print("QQQ_WS_HANDSHAKE=FAIL",flush=True)
        print("QQQ_WS_ERROR="+type(exc).__name__,flush=True)
    print("QQQ_WS_CHECK_SECONDS="+str(round(time.monotonic()-started,2)),flush=True)

asyncio.run(main())
