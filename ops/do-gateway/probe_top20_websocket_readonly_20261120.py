"""Read-only smoke check for the deployed QQQ and TOP20 quote origin."""
import asyncio
import json
import urllib.request

origin = "https://gaemigtp-main.pages.dev"
with urllib.request.urlopen("http://127.0.0.1:8765/market/trading-value?market=us", timeout=8) as body:
    ranked = json.load(body)
industries = set(["AAPL","AAPL.O","AMAT","AMAT.O","AMD","AMD.O","AMZN","AMZN.O","ASML","ASML.O","AVGO","AVGO.O","BA","BABA","BE","BRZE.O","CLX","CRCL.K","CRDO","CRWD","CRWV","CRWV.O","CSCO","DELL","DELL.K","EQIX","FER","GE","GEV","GMAB","GOOG","GOOG.O","GOOGL","GOOGL.O","HOOD","HSBC","IBM","INTC","INTC.O","IONQ.K","IREN","IREN.O","JNJ","JPM","KEYS","LITE","LITE.O","LLY","LRCX","LRCX.O","LULU.O","MELI","META","META.O","MRNA","MRNA.O","MRVL","MRVL.O","MSFT","MSFT.O","MSTR","MU","MU.O","NBIS","NBIS.O","NFLX.O","NOW","NVDA","NVDA.O","NVS","ORCL","ORCL.K","PANW","PG","PLTR","PLTR.O","RBNE.O","RKLB.O","SAP","SKHY","SKHY.O","SLN.O","SMCI.O","SMR","SNDK","SNDK.O","SOFI","SPCX","SPCX.O","STX","TSLA","TSLA.O","TSM","UBER","V","WDC","XXII.O"])
assert ranked["ok"] and len(ranked["items"]) == 20
symbols = {row["symbol"] for row in ranked["items"]}
aliases = {"ND": ".O", "NY": ".K"}
missing = [row["symbol"] for row in ranked["items"]
           if row["symbol"] not in industries and not row.get("industry")
           and not (row.get("exchange") in aliases and "." not in row["symbol"]
                    and row["symbol"] + aliases[row["exchange"]] in industries)]
print("TOP20_INDUSTRY_MISSING=" + (",".join(missing) or "none"), flush=True)

async def main():
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets.client import connect

    async with connect("wss://quotes.gaemigtp.com/ws/us-live-quotes", origin=origin,
                       open_timeout=10, close_timeout=2, max_size=16384, ping_interval=None) as ws:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 20
        qqq = False
        seen = set()
        frames = set()
        while (remaining := deadline - loop.time()) > 0:
            try:
                value = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
            except asyncio.TimeoutError:
                break
            frames.add(value["type"])
            if value["type"] == "quote" and value.get("quote"):
                quote = value["quote"]
                assert quote["symbol"] == "QQQ" and quote["price"] > 0
                qqq = qqq or not quote["stale"]
            if value["type"] == "quotes":
                assert len(value["items"]) <= 20
                for quote in value["items"]:
                    if not quote["stale"] and quote["symbol"] in symbols:
                        assert quote["price"] > 0 and quote["received_at_ms"] > 0
                        seen.add(quote["symbol"])
            if qqq and len(seen) == 20:
                break
        assert {"quote", "quotes"} <= frames, frames
        print(f"PUBLIC_TOP20_WS_FRESH={len(seen)} PUBLIC_QQQ_WS_FRESH={int(qqq)}", flush=True)

asyncio.run(main())
