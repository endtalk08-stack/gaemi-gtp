"""Read-only check Render market-close API after Neon publish; no secrets or edits."""
import urllib.request,urllib.error,json,sys,os
sys.path.insert(0,os.getcwd())
from backend.services import us_market_close
print("CLOSE_INPUT_LIMIT",("[:1300]" in __import__("inspect").getsource(us_market_close._prompt)),flush=True)
print("CLOSE_STRICT_SCHEMA",('"strict": True' in __import__("inspect").getsource(us_market_close._generate)),flush=True)
result=us_market_close.read_brief()
print("NEON_CLOSE_VISIBLE",bool(result),flush=True)
if result:
 print("NEON_CLOSE_SESSION",result.get("session_date"),"CONTENT_CHARS",len(result.get("content") or ""),"HAS_PRESENTATION",bool(result.get("presentation")),flush=True)
req=urllib.request.Request("https://gaemi-gtp.onrender.com/api/market/us-close",headers={"Accept":"application/json","User-Agent":"gaemiGTP-us-close-verifier/1.0"})
try:
 with urllib.request.urlopen(req,timeout=15) as resp:
  body=resp.read(200000)
  print("RENDER_CLOSE_HTTP",resp.status,"CONTENT_TYPE",resp.headers.get("Content-Type"),flush=True)
 data=json.loads(body)
 print("RENDER_CLOSE_JSON",json.dumps({"ok":data.get("ok"),"session_date":data.get("session_date"),"keys":list(data.keys()),"content_chars":len(str(data.get("content") or ""))},ensure_ascii=False),flush=True)
except urllib.error.HTTPError as e:
 print("RENDER_CLOSE_HTTP_ERROR",e.code,str(e.read(250).decode("utf-8","replace"))[:100],flush=True)
except Exception as e:
 print("RENDER_CLOSE_ERROR",type(e).__name__,str(e)[:160],flush=True)
