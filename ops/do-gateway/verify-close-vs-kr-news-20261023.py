"""Read-only verify Naver/US-close code paths and execution error on DigitalOcean."""
import os,sys,pathlib,re,subprocess,json
base=pathlib.Path("/opt/gaemigtp-news/app")
paths={"worker":base/"backend/news_worker.py","market_close":base/"backend/services/us_market_close.py","close_runtime":base/"backend/services/us_market_close_runtime.py","naver_provider":base/"backend/providers/naver_news.py"}
for label,path in paths.items():
 try:
  data=path.read_text()
  print("FILE",label,"exists=True","bytes",len(data),flush=True)
  if label=="worker":
   print("WORKER_US_ONLY",('if market != "미국"' in data),"WORKER_NEWS_RESTORED",("news_feed.fetch_stock_news" in data),"RANKING_US_ONLY",('("국내",' not in data),flush=True)
  if label=="market_close":
   print("CLOSE_NEWS_CALLS_VERIFIED_ORIGINALS",("verified_originals(session_date" in data),"CLOSE_USES_GROQ",("https://api.groq.com/openai/v1/chat/completions" in data),"CLOSE_USES_WORKER",("news_worker" in data),"MODEL_120B",('openai/gpt-oss-120b' in data),flush=True)
  if label=="close_runtime":
   print("RUNTIME_USES_NAVER_NEWS_DIRECT",("from backend.providers.naver_news import fetch_news" in data),"RUNTIME_USES_WORKER",("news_worker" in data),flush=True)
 except Exception as e:print("READ_ERROR",label,type(e).__name__,flush=True)
for name in ("NAVER_CLIENT_ID","NAVER_CLIENT_SECRET","GROQ_API_KEY"):
 print("ENV_CONFIGURED",name,bool(os.environ.get(name,"").strip()),flush=True)
for unit in ("gaemigtp-news.service","gaemigtp-us-market-close.service"):
 r=subprocess.run(["systemctl","show",unit,"-p","FragmentPath","-p","ActiveState","-p","SubState"],capture_output=True,text=True,timeout=5)
 print("UNIT_STATUS",unit,repr(r.stdout.strip()),flush=True)
r=subprocess.run(["journalctl","--no-pager","-u","gaemigtp-us-market-close.service","--since","2026-10-22 21:59:00 UTC","--until","2026-10-22 22:05:00 UTC","-o","cat"],capture_output=True,text=True,timeout=8)
for line in r.stdout.splitlines():
 if any(s in line for s in ("us-close","us_market_close_failed","FAILURE","search=")):
  print("CLOSE_LOG",line[:350],flush=True)
