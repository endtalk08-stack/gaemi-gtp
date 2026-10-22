"""Diagnostic: compare Groq 120B completion from DO with close/admin User-Agent; stop at first success."""
import os,sys,json,urllib.request,urllib.error,subprocess
MODEL="openai/gpt-oss-120b"
key=os.environ.get("GROQ_API_KEY","").strip()
if not key:
 print("NO_GROQ_KEY");sys.exit(0)
payload={"model":MODEL,"messages":[{"role":"user","content":"Reply with exactly OK."}],"temperature":0,"max_completion_tokens":128,"reasoning_effort":"low","stream":False}
body=json.dumps(payload).encode("utf-8")
url="https://api.groq.com/openai/v1/chat/completions"
for ua in ("gaemiGTP-us-close/1.0","gaemiGTP-ai-test/1.0","Mozilla/5.0 (compatible; gaemiGTP/1.0)"):
 req=urllib.request.Request(url,data=body,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","User-Agent":ua},method="POST")
 try:
  with urllib.request.urlopen(req,timeout=18) as r:
   obj=json.load(r)
   msg=(obj.get("choices") or [{}])[0].get("message") or {}
   print("GROQ_POST_OK",ua,"HTTP",r.status,"MODEL",obj.get("model"),"USAGE",json.dumps(obj.get("usage") or {}),"ANSWER_CHARS",len(str(msg.get("content") or "")),flush=True)
  sys.exit(0)
 except urllib.error.HTTPError as e:
  b=e.read(1000).decode("utf-8","replace")
  print("GROQ_POST_HTTP_ERROR",ua,"HTTP",e.code,"BODY",b[:420],flush=True)
  if e.code not in (403,429):break
  if e.code==429:break
 except Exception as e:
  print("GROQ_POST_OTHER",ua,type(e).__name__,str(e)[:170],flush=True)
  break
print("GROQ_TEST_DONE",flush=True)
