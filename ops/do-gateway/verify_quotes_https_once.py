"""Verify local and Cloudflare-facing HTTPS TOP20 without writes or market calls."""
import json, ssl, urllib.request, urllib.error, socket, subprocess
from urllib.parse import urljoin

host="quotes.gaemigtp.com"
paths=("/health","/market/trading-value?market=us")
print("TOP20_HTTPS_PROBE_BEGIN")
for mode,base,ctx in (
    ("origin-local","https://127.0.0.1",ssl._create_unverified_context()),
    ("cloudflare-external","https://"+host,ssl.create_default_context()),
):
    for path in paths:
        url=base+path
        try:
            with urllib.request.urlopen(url,timeout=12,context=ctx) as resp:
                body=json.loads(resp.read(60000).decode("utf-8"))
                status=resp.status
            print("PROBE_MODE="+mode+" PATH="+path.split("?")[0]+" HTTP="+str(status)+" OK="+str(body.get("ok"))+
                  " COUNT="+str(len(body.get("items",[])))+
                  " VALUE_PRESENT="+str(sum(isinstance(x.get("trading_value"),(int,float)) for x in body.get("items",[]))),flush=True)
        except Exception as exc:
            print("PROBE_MODE="+mode+" PATH="+path.split("?")[0]+" ERROR="+type(exc).__name__+
                  " DETAIL="+str(exc)[:120],flush=True)
try:
    print("DNS_CF="+str(socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)[0][4][0]))
except Exception as exc: print("DNS_FAIL="+type(exc).__name__+" "+str(exc)[:80])
for unit in ("gaemigtp-kiwoom-us-top20-api.service","gaemigtp-kiwoom-us-top20-https.service"):
    p=subprocess.run(["systemctl","show",unit,"-p","ActiveState","-p","SubState"],capture_output=True,text=True,timeout=5)
    print("UNIT="+unit+" "+p.stdout.strip().replace("\\n"," "))
print("TOP20_HTTPS_PROBE_END")
