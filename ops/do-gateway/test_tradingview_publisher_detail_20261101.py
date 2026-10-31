"""Inspect one normal publisher article via list + detail API.
Never reads or requests storyPath. No worker, DB, AI, or file writes.
"""
import json,os,urllib.parse,urllib.request,subprocess

def get_json(url,key):
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=15) as r:
        return r.status,json.loads(r.read(2_000_000).decode("utf-8"))

assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True).stdout.strip()=="inactive"
key=os.environ["TRADINGVIEW_API_KEY"].strip()
base="https://api.tradingviewapi.com"
status,feed=get_json(base+"/api/news/stock?symbol=NASDAQ%3AAAPL&lang=en",key)
print("PUBLISHER_LIST_STATUS",status,flush=True)
data=feed.get("data") or {}
items=data.get("items") if isinstance(data,dict) else None
if not isinstance(items,list):
    print("PUBLISHER_LIST_SHAPE",sorted(feed.keys()) if isinstance(feed,dict) else type(feed).__name__,flush=True)
    raise SystemExit(2)
print("PUBLISHER_LIST_COUNT",len(items),flush=True)
selected=None
for i,item in enumerate(items[:30]):
    if not isinstance(item,dict): continue
    provider=item.get("provider") or {}
    pname=provider.get("name") if isinstance(provider,dict) else str(provider)
    direct=next((item.get(k) for k in ("link","url","originalUrl","original_url","sourceUrl","source_url") if isinstance(item.get(k),str) and item.get(k).startswith(("https://","http://"))),None)
    print("PUBLISHER_ITEM",i,"ID",str(item.get("id") or "")[:180],
          "PROVIDER",str(pname)[:80],"TITLE",str(item.get("title") or "")[:180],
          "DIRECT_URL_FIELD",bool(direct),"FIELDS",sorted(item.keys()),flush=True)
    if selected is None and item.get("id") and str(pname).lower() not in ("quartr","tradingview"):
        selected=(item,pname,direct)
if selected is None:
    print("NO_NON_QUARTR_PUBLISHER_ITEM",flush=True)
else:
    item,pname,direct=selected
    nid=str(item["id"])
    url=base+"/api/news/"+urllib.parse.quote(nid,safe="")+"?lang=en"
    st,detail=get_json(url,key)
    d=detail.get("data") or {}
    print("PUBLISHER_DETAIL_STATUS",st,flush=True)
    print("PUBLISHER_DETAIL_KEYS",sorted(d.keys()) if isinstance(d,dict) else type(d).__name__,flush=True)
    print("PUBLISHER_PROVIDER",pname,flush=True)
    for field in ("title","shortDescription","description","content","body","text","article","copyright","language","read_time"):
        val=d.get(field) if isinstance(d,dict) else None
        if isinstance(val,str):
            print("PUBLISHER_DETAIL_FIELD",field,"LEN",len(val),"PREVIEW",repr(val[:1000]),flush=True)
        elif val is not None:
            print("PUBLISHER_DETAIL_FIELD",field,"TYPE",type(val).__name__,flush=True)
    urls=[]
    def scan(v,path="$",depth=0):
        if depth>6:return
        if isinstance(v,dict):
            for k,x in v.items():
                lk=str(k).lower()
                if any(t in lk for t in ("url","link","original","source")) and isinstance(x,str) and x.startswith(("http://","https://")):
                    urls.append((path+"."+str(k),x))
                if isinstance(x,(dict,list)):scan(x,path+"."+str(k),depth+1)
        elif isinstance(v,list):
            for n,x in enumerate(v):scan(x,path+"["+str(n)+"]",depth+1)
    scan(d)
    print("PUBLISHER_DETAIL_EXTERNAL_URLS",len(urls),flush=True)
    for path,u in urls[:20]:
        print("PUBLISHER_URL",path,u[:500],flush=True)
    def strings(v,out,depth=0):
        if depth>8:return
        if isinstance(v,str):
            if v.strip():out.append(v.strip())
        elif isinstance(v,dict):
            for x in v.values():strings(x,out,depth+1)
        elif isinstance(v,list):
            for x in v:strings(x,out,depth+1)
    txt=[]
    if isinstance(d,dict):
        for field in ("astDescription","content","body","article","text","description"):
            if field in d:strings(d[field],txt)
    merged="\n".join(dict.fromkeys(txt))
    print("PUBLISHER_RICH_TEXT_LEN",len(merged),flush=True)
    print("PUBLISHER_RICH_TEXT_PREVIEW",repr(merged[:1800]),flush=True)
assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True).stdout.strip()=="inactive"
print("PUBLISHER_ARTICLE_CHECK_DONE_WORKER_INACTIVE",flush=True)
