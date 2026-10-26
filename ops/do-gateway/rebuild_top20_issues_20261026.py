"""Rebuild current 20 stock code issues using deployed pipeline; no AI calls."""
import sys,os,json
from pathlib import Path
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services import news_feed,news_processed_store as store
from backend.services.news_result import build_stock_news_result
state=json.loads(Path("/var/lib/gaemigtp-news/rotation.json").read_text())
params=dict(market="미국",limit=50,storyboard_limit=3,display_timezone="Asia/Seoul")
for item in state["cycle"]:
 name=item["name"]
 try:
  raw=news_feed.fetch_stock_news(name,market="미국",limit=50,raise_on_error=True)
  if not raw: raise RuntimeError("empty_news")
  result=build_stock_news_result(name,raw_news_list=raw,**params)
  if result.get("_news_status")!="ok": raise RuntimeError("code_analysis_failed")
  store.save_snapshot(name,fingerprint=store.source_fingerprint(raw),result=result,**params)
  briefs=result.get("issue_briefs") or []
  print("TOP20_REBUILD",json.dumps({"stock":name,"symbol":item["symbol"],"status":"saved","issues":len(briefs),"missing_tags":sum(not b.get("tags") for b in briefs)},ensure_ascii=False),flush=True)
 except Exception as exc:
  print("TOP20_REBUILD",json.dumps({"stock":name,"symbol":item["symbol"],"status":"failed","error":type(exc).__name__},ensure_ascii=False),flush=True)
