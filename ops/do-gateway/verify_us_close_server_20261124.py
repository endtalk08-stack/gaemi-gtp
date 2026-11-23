#!/usr/bin/env python3
"""Read-only verification of the deployed close-hold code and quote API."""
import ast, hashlib, json, pathlib, subprocess, urllib.request
p=pathlib.Path("/opt/gaemigtp-news/app/backend/kiwoom_us_top20_api.py")
content=p.read_bytes()
sha=hashlib.sha1(("blob "+str(len(content))).encode()+bytes([0])+content).hexdigest()
print("SERVER_CODE_GIT_SHA",sha)
print("SERVER_CODE_MATCH",sha=="6bdaa13974a2b895c28d2b0d84774c8883886a15")
if sha!="6bdaa13974a2b895c28d2b0d84774c8883886a15":
    raise SystemExit("server_code_mismatch")
tree=ast.parse(content.decode("utf-8"))
required={"_us_close_phase","_us_close_get","_us_close_remember",
          "_get_market_widget_quotes","read_top20","_feed_snapshot"}
available={f.name for f in tree.body if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef))}
print("HOLD_FUNCTIONS_PRESENT",required <= available)
if not required <= available:
    raise SystemExit("server_missing_hold")
for name in ("gaemigtp-kiwoom-us-top20-api.service","gaemigtp-kiwoom-us-top20-https.service"):
    r=subprocess.run(["systemctl","is-active",name],capture_output=True,text=True,timeout=5)
    print("UNIT_ACTIVE",name,r.returncode==0,r.stdout.strip())
    if r.returncode:
        raise SystemExit("service_not_active")
for path in ("/health","/market/trading-value?market=us"):
    url="http://127.0.0.1:8765"+path
    with urllib.request.urlopen(url,timeout=12) as response:
        data=json.load(response)
    print("API",path,"ok",data.get("ok"),"items",len(data.get("items",[])))
    if not data.get("ok"):
        raise SystemExit("api_unhealthy")
    if path.startswith("/market/trading-value") and len(data.get("items",[])) != 20:
        raise SystemExit("top20_not_complete")
print("VERIFY_US_CLOSE_SERVER_OK")
