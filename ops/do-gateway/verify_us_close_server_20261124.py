#!/usr/bin/env python3
"""Read-only verification of the exact original quote API after rollback."""
import ast, hashlib, json, pathlib, subprocess, urllib.request
p=pathlib.Path("/opt/gaemigtp-news/app/backend/kiwoom_us_top20_api.py")
content=p.read_bytes()
sha=hashlib.sha1(("blob "+str(len(content))).encode()+bytes([0])+content).hexdigest()
print("SERVER_CODE_GIT_SHA",sha)
print("SERVER_CODE_MATCH",sha=="b81ac10864ea2dab00cfbba43100a980ba114a3f")
if sha!="b81ac10864ea2dab00cfbba43100a980ba114a3f":
    raise SystemExit("server_code_mismatch")
tree=ast.parse(content.decode("utf-8"))
original={"_get_us_industry_etf_quotes","_get_us_industry_map_with_stocks",
          "_get_market_widget_quotes","read_top20","_feed_snapshot"}
added={"_us_close_phase","_us_close_get","_us_close_remember"}
available={f.name for f in tree.body if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef))}
print("ORIGINAL_INDUSTRY_FUNCTIONS_PRESENT",original <= available)
print("ADDED_HOLD_FUNCTIONS_ABSENT",not (added & available))
if not original <= available or added & available:
    raise SystemExit("rollback_incomplete")
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
print("VERIFY_ORIGINAL_US_QUOTE_SERVER_OK")
