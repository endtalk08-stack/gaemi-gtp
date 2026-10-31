"""Inspect article-detail rich text tree; one request only, no storyPath fetch."""
import json,os,urllib.parse,urllib.request,subprocess
assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True).stdout.strip()=="inactive"
key=os.environ["TRADINGVIEW_API_KEY"].strip()
nid="urn:summary_document_slides:quartr.com:4269329:0"
url="https://api.tradingviewapi.com/api/news/"+urllib.parse.quote(nid,safe="")+"?lang=en"
req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"Accept":"application/json"})
with urllib.request.urlopen(req,timeout=15) as r:
    obj=json.loads(r.read(2_000_000).decode("utf-8"))
d=obj.get("data") or {}
print("DETAIL_FIELDS",sorted(d.keys()),flush=True)
for k in ("copyright","language","read_time","shortDescription","title"):
    v=d.get(k)
    if v is not None: print("DETAIL_VALUE",k,repr(v)[:1200],flush=True)
def flatten(v,out):
    if isinstance(v,dict):
        for k,x in v.items():
            if k in ("text","value","content","url","href","link","type") and isinstance(x,(str,int,float)):
                out.append((k,str(x)))
            if isinstance(x,(dict,list)):flatten(x,out)
    elif isinstance(v,list):
        for x in v:flatten(x,out)
tree=d.get("astDescription")
vals=[]
flatten(tree,vals)
print("AST_LEAF_COUNT",len(vals),flush=True)
for k,v in vals[:120]:
    print("AST_LEAF",k,repr(v[:1200]),flush=True)
# list keys containing any likely external/original URL field; never print storyPath
print("URL_FIELDS_PRESENT",[k for k in d if any(x in k.lower() for x in ("url","link","source","original","external")) and k!="storyPath"],flush=True)
print("PROVIDER",json.dumps(d.get("provider"),ensure_ascii=False),flush=True)
assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True).stdout.strip()=="inactive"
print("DETAIL_AST_INSPECTION_DONE",flush=True)
