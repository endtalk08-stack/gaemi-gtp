"""One live detail-endpoint check for an existing news id.
Does not request TradingView storyPath and does not start the worker.
"""
import json, os, urllib.parse, urllib.request, subprocess

assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],
    capture_output=True,text=True,timeout=10).stdout.strip()=="inactive"
key=os.environ.get("TRADINGVIEW_API_KEY","").strip()
assert key, "TRADINGVIEW_API_KEY_NOT_AVAILABLE"
news_id="urn:summary_document_slides:quartr.com:4269329:0"
url="https://api.tradingviewapi.com/api/news/"+urllib.parse.quote(news_id,safe="")+"?lang=en"
req=urllib.request.Request(url,headers={
    "Authorization":"Bearer "+key,
    "Accept":"application/json",
    "User-Agent":"gaemiGTP-news-detail-check/1.0",
},method="GET")
try:
    with urllib.request.urlopen(req,timeout=15) as res:
        status=res.status
        raw=res.read(2_000_000)
except Exception as exc:
    print("DETAIL_HTTP_ERROR",type(exc).__name__,flush=True)
    raise SystemExit(2)
print("DETAIL_HTTP_STATUS",status,flush=True)
print("DETAIL_BYTES",len(raw),flush=True)
try:
    obj=json.loads(raw.decode("utf-8"))
except Exception as exc:
    print("DETAIL_JSON_ERROR",type(exc).__name__,flush=True)
    print("DETAIL_BODY_PREFIX",raw[:500].decode("utf-8","replace"),flush=True)
    raise SystemExit(3)
print("DETAIL_TOP_TYPE",type(obj).__name__,flush=True)
def walk(v,path="$",depth=0):
    if depth>5:return
    if isinstance(v,dict):
        print("DETAIL_KEYS",path,sorted(map(str,v.keys()))[:100],flush=True)
        for k,val in v.items():
            lk=str(k).lower()
            if any(t in lk for t in ("content","body","article","text","url","link","source","provider","title","description","summary","story","id")):
                if isinstance(val,str):
                    print("DETAIL_FIELD",path+"."+str(k),"LEN",len(val),"PREVIEW",repr(val[:1200]),flush=True)
                elif isinstance(val,(int,float,bool)) or val is None:
                    print("DETAIL_FIELD",path+"."+str(k),repr(val)[:300],flush=True)
                elif isinstance(val,list):
                    print("DETAIL_FIELD",path+"."+str(k),"LIST",len(val),flush=True)
                elif isinstance(val,dict):
                    print("DETAIL_FIELD",path+"."+str(k),"OBJECT",sorted(map(str,val.keys()))[:80],flush=True)
            if isinstance(val,(dict,list)):
                walk(val,path+"."+str(k),depth+1)
    elif isinstance(v,list):
        print("DETAIL_ARRAY",path,"COUNT",len(v),flush=True)
        if v:walk(v[0],path+"[0]",depth+1)
walk(obj)
assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],
    capture_output=True,text=True,timeout=10).stdout.strip()=="inactive"
print("DETAIL_CHECK_COMPLETE_WORKER_INACTIVE",flush=True)
