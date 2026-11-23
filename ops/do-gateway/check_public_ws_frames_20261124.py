#!/usr/bin/env python3
"""Read-only check of public websocket freshness. No market prices or credentials logged."""
import os, ssl, socket, base64, struct, json, datetime, time
HOST="quotes.gaemigtp.com";ORIGIN="https://gaemigtp-main.pages.dev"
def check(target):
    key=base64.b64encode(os.urandom(16)).decode("ascii")
    sock=socket.create_connection((target,443),timeout=7)
    ctx=ssl.create_default_context()
    if target=="127.0.0.1":
        ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
    s=ctx.wrap_socket(sock,server_hostname=HOST)
    s.settimeout(7)
    request=("GET /ws/us-live-quotes HTTP/1.1\r\nHost: "+HOST+"\r\nOrigin: "+ORIGIN
        +"\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: "+key
        +"\r\nSec-WebSocket-Version: 13\r\n\r\n")
    s.sendall(request.encode("ascii"))
    response=b""
    while b"\r\n\r\n" not in response and len(response)<6000:
        response+=s.recv(4096)
    headers,_,remaining=response.partition(b"\r\n\r\n")
    print("WS_HANDSHAKE",target,headers.split(b"\r\n",1)[0].decode("utf8","replace"),flush=True)
    if b" 101 " not in headers.split(b"\r\n",1)[0]:
        s.close();return
    buf=remaining
    def take(n):
        nonlocal buf
        while len(buf)<n:
            more=s.recv(max(2048,n-len(buf)))
            if not more:raise EOFError("connection_closed")
            buf+=more
        x,buf=buf[:n],buf[n:];return x
    samples=0
    while samples<8:
        b0,b1=take(2)
        length=b1&127
        if length==126:length=struct.unpack("!H",take(2))[0]
        elif length==127:length=struct.unpack("!Q",take(8))[0]
        if length>150000:raise ValueError("frame_too_big")
        if b1&128:take(4)
        payload=take(length)
        if b0&15!=1:continue
        item=json.loads(payload)
        typ=item.get("type")
        if typ=="quote":rows=[item.get("quote")] if item.get("quote") else []
        else:rows=item.get("items") if isinstance(item.get("items"),list) else []
        valid=[q for q in rows if isinstance(q,dict)]
        pct=sum(isinstance(x.get("change_pct"),(int,float)) for x in valid)
        fresh=sum(x.get("stale") is False for x in valid)
        recent=sum(isinstance(x.get("received_at_ms"),(int,float)) and abs(time.time()*1000-x["received_at_ms"])<30000 for x in valid)
        print("WS_FRAME",target,typ,"items",len(valid),"pct",pct,"fresh",fresh,"received_recent30s",recent,flush=True)
        samples+=1
    s.close()
for target in ("127.0.0.1",HOST):
    try:check(target)
    except Exception as ex:print("WS_ERROR",target,type(ex).__name__,str(ex)[:120],flush=True)
print("WS_READONLY_DONE")
