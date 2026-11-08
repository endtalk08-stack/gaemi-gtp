"""One read-only TradingView detail request after a headline-only pass."""
import json,os,re,subprocess,urllib.error,urllib.parse,urllib.request
def inactive(u):
    p=subprocess.run(["systemctl","is-active",u],text=True,capture_output=True,timeout=5)
    return p.stdout.strip()=="inactive"
units=("gaemigtp-news.service","gaemigtp-tradingview-news.service")
if any(not inactive(u) for u in units):
    raise SystemExit("TV_STOP_NEWS_WORKER_ACTIVE")
key=os.environ.get("TRADINGVIEW_API_KEY","").strip()
if not key:
    raise SystemExit("TV_STOP_API_KEY_MISSING")
# The saved Korean headline passed the economic title-only filter.
news_id="tag:reuters.com,2026:newsml_L3N46N1G1:0"
url="https://api.tradingviewapi.com/api/news/"+urllib.parse.quote(news_id,safe="")+"?lang=ko"
req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"Accept":"application/json"})
print("TV_DETAIL_CALL_BUDGET=1 LANG=ko TITLE_FILTER=pass",flush=True)
try:
    with urllib.request.urlopen(req,timeout=15) as resp:
        status=resp.status
        raw=resp.read(2500000)
except urllib.error.HTTPError as e:
    print("TV_DETAIL_STOP_HTTP_STATUS="+str(e.code)+" RETRY=0",flush=True)
    raise SystemExit(2)
except (OSError,TimeoutError) as e:
    print("TV_DETAIL_STOP_NETWORK_ERROR="+type(e).__name__+" RETRY=0",flush=True)
    raise SystemExit(2)
if status!=200:
    raise SystemExit("TV_DETAIL_STOP_UNEXPECTED_STATUS")
obj=json.loads(raw.decode("utf-8"))
if not isinstance(obj,dict) or obj.get("success") is not True or not isinstance(obj.get("data"),dict):
    raise SystemExit("TV_DETAIL_STOP_INVALID_SCHEMA")
data=obj["data"]
parts=[]
def flatten(node,depth=0):
    if depth>15 or len(parts)>10000:
        return
    if isinstance(node,dict):
        for k,v in node.items():
            if k in ("text","value","plainText","content") and isinstance(v,str) and v.strip():
                parts.append(v.strip()[:10000])
            elif isinstance(v,(dict,list)):
                flatten(v,depth+1)
    elif isinstance(node,list):
        for v in node[:2000]:
            flatten(v,depth+1)
flatten(data.get("astDescription"))
plain=" ".join(parts)
cand={k:len(str(data.get(k) or "")) for k in ("body","articleBody","fullText","content","description","shortDescription","summary")}
print("TV_DETAIL_KO_PROBE="+json.dumps({
    "http":status,
    "data_keys":sorted(data.keys())[:100],
    "title_has_ko":bool(re.search("[가-힣]",str(data.get("title") or ""))),
    "title_present":bool(data.get("title")),
    "permission":str(data.get("permission") or "unset")[:30],
    "ast_type":type(data.get("astDescription")).__name__,
    "ast_text_segments":len(parts),
    "ast_text_chars":len(plain),
    "ast_contains_ko":bool(re.search("[가-힣]",plain)),
    "body_candidate_lengths":cand,
    "network_calls":1,
    "cache_writes":0,
    "r2_writes":0,
},ensure_ascii=False,separators=(",",":")),flush=True)
if any(not inactive(u) for u in units):
    raise SystemExit("TV_STOP_WORKER_STATE_CHANGED")
print("TV_DETAIL_KO_PROBE_DONE_ONE_CALL",flush=True)
