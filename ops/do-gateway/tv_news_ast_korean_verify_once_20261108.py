"""Verify Korean full-text presence in TradingView astDescription, read-only, one call."""
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

UNITS=("gaemigtp-news.service","gaemigtp-tradingview-news.service")
def unit_stopped(unit):
    p=subprocess.run(("systemctl","is-active",unit),text=True,capture_output=True,timeout=6)
    return p.stdout.strip()=="inactive"
if any(not unit_stopped(u) for u in UNITS):
    raise SystemExit("STOP_ACTIVE_NEWS_WORKER")
key=os.environ.get("TRADINGVIEW_API_KEY","").strip()
if not key:
    raise SystemExit("STOP_MISSING_API_KEY")
nid="tag:reuters.com,2026:newsml_L3N46N1G1:0"
url="https://api.tradingviewapi.com/api/news/"+urllib.parse.quote(nid,safe="")+"?lang=ko"
req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"Accept":"application/json","User-Agent":"gaemiGTP-AST-Korean-check/1.0"})
print("AST_KO_VERIFY_BUDGET=1; NO_RETRY=1",flush=True)
try:
    with urllib.request.urlopen(req,timeout=15) as response:
        status=response.status
        payload=json.loads(response.read(2500000).decode("utf-8"))
except urllib.error.HTTPError as e:
    print("AST_KO_VERIFY_STOP_HTTP="+str(e.code),flush=True)
    raise SystemExit(2)
except Exception as e:
    print("AST_KO_VERIFY_STOP_EXCEPTION="+type(e).__name__,flush=True)
    raise SystemExit(2)
if status!=200 or payload.get("success") is not True or not isinstance(payload.get("data"),dict):
    raise SystemExit("AST_KO_VERIFY_BAD_SCHEMA")
data=payload["data"]
ast=data.get("astDescription")
def walk(node, depth=0):
    if depth>40:
        return []
    if isinstance(node,str):
        return [node] if node.strip() else []
    if isinstance(node,list):
        results=[]
        for item in node[:5000]:
            results.extend(walk(item, depth+1))
        return results
    if isinstance(node,dict):
        if isinstance(node.get("children"),list):
            return walk(node["children"],depth+1)
        for key in ("text","plainText","value","content"):
            if isinstance(node.get(key),str) and node[key].strip():
                return [node[key]]
        return []
    return []
strings=walk(ast)
body=" ".join(s.strip() for s in strings if s.strip())
desc=str(data.get("shortDescription") or "")
body_norm=re.sub(r"\\s+"," ",body).strip()
desc_norm=re.sub(r"\\s+"," ",desc).strip()
ko_count=len(re.findall("[가-힣]",body_norm))
node_details=[]
if isinstance(ast,dict):
    for node in (ast.get("children") or [])[:8]:
        node_details.append({"type":str(node.get("type") or "") if isinstance(node,dict) else type(node).__name__,
                             "child_type":type(node.get("children")).__name__ if isinstance(node,dict) else "",
                             "child_count":len(node.get("children") or []) if isinstance(node,dict) else 0})
report={"id":nid,"http":status,
        "response_language":data.get("language"),
        "ast_type":type(ast).__name__,
        "ast_root_keys":list(ast.keys())[:12] if isinstance(ast,dict) else [],
        "ast_child_nodes":len(ast.get("children") or []) if isinstance(ast,dict) else None,
        "ast_sample_shapes":node_details,
        "ast_text_leaves":len(strings),
        "ast_text_chars":len(body_norm),
        "ast_korean_chars":ko_count,
        "ast_korean_present":ko_count>0,
        "description_chars":len(desc_norm),
        "ast_equals_description":body_norm==desc_norm,
        "ast_contains_description":bool(desc_norm and desc_norm in body_norm),
        "ast_longer_than_description":len(body_norm)>len(desc_norm)+100,
        "permission":data.get("permission"),
        "network_calls":1,"r2_writes":0,"db_writes":0,"local_cache_writes":0}
print("AST_KO_VERIFY_RESULT="+json.dumps(report,ensure_ascii=False,separators=(",",":")),flush=True)
if any(not unit_stopped(u) for u in UNITS):
    raise SystemExit("STOP_NEWS_WORKER_STATE_CHANGED")
print("AST_KO_VERIFY_FINISHED_WORKERS_STOPPED",flush=True)
