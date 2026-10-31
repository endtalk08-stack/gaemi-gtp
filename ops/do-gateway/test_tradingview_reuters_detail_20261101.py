"""Inspect Reuters detail for a headline with no direct link in the stock list.
Never requests storyPath. No worker, DB, AI, or writes.
"""
import json,os,urllib.parse,urllib.request,subprocess
assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True).stdout.strip()=="inactive"
key=os.environ["TRADINGVIEW_API_KEY"].strip()
nid="tag:reuters.com,2026:newsml_L6N46G031:0"
url="https://api.tradingviewapi.com/api/news/"+urllib.parse.quote(nid,safe="")+"?lang=en"
req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"Accept":"application/json"})
try:
    with urllib.request.urlopen(req,timeout=15) as r:
        status=r.status; d=json.loads(r.read(2_000_000).decode("utf-8")).get("data") or {}
except Exception as exc:
    print("REUTERS_DETAIL_ERROR",type(exc).__name__,flush=True); raise SystemExit(2)
print("REUTERS_DETAIL_STATUS",status,flush=True)
print("REUTERS_DETAIL_KEYS",sorted(d.keys()),flush=True)
for k in ("title","shortDescription","summary","description","content","body","text","copyright","language","read_time","link","canonical_link"):
    v=d.get(k)
    if isinstance(v,str):
        print("REUTERS_FIELD",k,"LEN",len(v),"VALUE",repr(v[:1000]),flush=True)
    elif v is not None: print("REUTERS_FIELD",k,"TYPE",type(v).__name__,flush=True)
def strings(v,out,depth=0):
    if depth>8:return
    if isinstance(v,str):
        if v.strip():out.append(v.strip())
    elif isinstance(v,dict):
        for x in v.values():strings(x,out,depth+1)
    elif isinstance(v,list):
        for x in v:strings(x,out,depth+1)
out=[]
strings(d.get("astDescription"),out)
text="\n".join(dict.fromkeys(out))
print("REUTERS_AST_TEXT_LEN",len(text),flush=True)
print("REUTERS_AST_TEXT_PREVIEW",repr(text[:2000]),flush=True)
print("REUTERS_PROVIDER",json.dumps(d.get("provider"),ensure_ascii=False),flush=True)
assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True).stdout.strip()=="inactive"
print("REUTERS_DETAIL_DONE_WORKER_INACTIVE",flush=True)
