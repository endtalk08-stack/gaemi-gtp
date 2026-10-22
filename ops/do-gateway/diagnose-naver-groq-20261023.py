"""Read-only diagnostics for Naver US stock news and Groq model availability. No generation call."""
import json,os,sys,urllib.request,urllib.error
sys.path.insert(0,os.getcwd())
from backend.providers import naver_news
print("NAVER_CONFIGURED",naver_news.is_configured(),flush=True)
for term in ("엔비디아","NVIDIA","뉴욕증시 마감"):
    try:
        rows=naver_news.search_news(term,display=3,raise_on_error=True)
        print("NEWS_QUERY",term,"COUNT",len(rows),json.dumps([{"title":str(x.get("title") or "")[:90],"link":str(x.get("originallink") or "")[:150]} for x in rows],ensure_ascii=False),flush=True)
    except Exception as e:
        print("NEWS_QUERY_ERROR",term,type(e).__name__,str(e)[:120],flush=True)
key=os.environ.get("GROQ_API_KEY","").strip()
print("GROQ_KEY_PRESENT",bool(key),flush=True)
if key:
    req=urllib.request.Request("https://api.groq.com/openai/v1/models",headers={"Authorization":"Bearer "+key,"Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=12) as r:
            data=json.loads(r.read(150000))
            models=[str(x.get("id") or "") for x in data.get("data",[])]
            print("GROQ_MODELS_HTTP",r.status,"COUNT",len(models),"HAS_GPT_OSS_120B","openai/gpt-oss-120b" in models,flush=True)
    except urllib.error.HTTPError as e:
        print("GROQ_MODELS_ERROR_HTTP",e.code,str(e.read(300).decode("utf8","replace"))[:250],flush=True)
    except Exception as e:
        print("GROQ_MODELS_ERROR",type(e).__name__,str(e)[:150],flush=True)
