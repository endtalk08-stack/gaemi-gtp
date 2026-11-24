#!/usr/bin/env python3
from pathlib import Path
import os,subprocess,base64,json,socket,ssl,struct,time
p=Path("/opt/gaemigtp-news/app/backend/kiwoom_us_top20_api.py")
print("UID",os.geteuid(),"FILE_WRITABLE",os.access(p,os.W_OK),flush=True)
for i,l in enumerate(p.read_text().splitlines(),1):
 if 166<=i<=244 or 695<=i<=742: print("API",i,l[:180],flush=True)
p2=Path("/opt/gaemigtp-news/app/backend/kiwoom_us_live_prices.py")
for i,l in enumerate(p2.read_text().splitlines(),1):
 if 290<=i<=366: print("FE",i,l[:180],flush=True)
try:
 r=subprocess.run(["systemctl","show","gaemigtp-kiwoom-us-top20-https.service","-p","EnvironmentFiles","-p","User"],capture_output=True,text=True,timeout=4)
 print("SERVICE",r.stdout.strip()[:600],flush=True)
except Exception as ex:print("SERVICE_UNAVAIL",type(ex).__name__,flush=True)
try:
 c=ssl._create_unverified_context()
 sock=c.wrap_socket(socket.create_connection(("127.0.0.1",443),timeout=4),server_hostname="quotes.gaemigtp.com")
 sock.settimeout(6)
 key=base64.b64encode(os.urandom(16)).decode()
 sock.sendall(("GET /ws/us-live-quotes HTTP/1.1\r\nHost: quotes.gaemigtp.com\r\nOrigin: https://gaemigtp-main.pages.dev\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: "+key+"\r\n\r\n").encode())
 buf=b""
 while b"\r\n\r\n" not in buf:buf+=sock.recv(4096)
 buf=buf.split(b"\r\n\r\n",1)[1]
 until=time.monotonic()+9
 while time.monotonic()<until:
  while len(buf)<2:buf+=sock.recv(4096)
  n=buf[1]&127; k=2
  if n==126:
   while len(buf)<4:buf+=sock.recv(4096)
   n=struct.unpack("!H",buf[2:4])[0];k=4
  elif n==127:
   while len(buf)<10:buf+=sock.recv(4096)
   n=struct.unpack("!Q",buf[2:10])[0];k=10
  while len(buf)<k+n:buf+=sock.recv(4096)
  msg=json.loads(buf[k:k+n]);buf=buf[k+n:]
  if msg.get("type")=="industry-quotes":
   etfs={"IBIT","SOXX","XBI","XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY"}
   now=int(time.time()*1000)
   for x in msg.get("items",[]):
    if x.get("symbol") in etfs:
     print("WS_ETF",x["symbol"],"pct",x.get("change_pct"),"stale",x.get("stale"),"age_s",round((now-x.get("received_at_ms",now))/1000,1),"close",x.get("reference_close_date"),"session",x.get("reference_close_session"),flush=True)
   break
 sock.close()
except Exception as ex:print("WS_ERROR",type(ex).__name__,str(ex)[:120],flush=True)
