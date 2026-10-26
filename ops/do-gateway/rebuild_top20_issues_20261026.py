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
  print("TOP20_REBUILD",json.dumps({"stock":name,"symbol":item["symbol"],"status":"saved","issues":len(briefs),"missing_tags":sum(not b.get("tags") for b in briefs),"original_body_verified":sum(bool(b.get("_original_body_excerpt")) for b in briefs)},ensure_ascii=False),flush=True)
 except Exception as exc:
  print("TOP20_REBUILD",json.dumps({"stock":name,"symbol":item["symbol"],"status":"failed","error":type(exc).__name__},ensure_ascii=False),flush=True)

from backend.services.news_detail import read_selected_article_details
from backend.services.issue_briefs import _article_excerpt
import psycopg
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 conn.execute("SET TRANSACTION READ ONLY")
 with conn.cursor() as cur:
  cur.execute("SELECT stock_name,result_payload FROM public.news_processed_snapshots WHERE market='미국' AND stock_name IN ('엔비디아','마이크론 테크놀로지','스페이스X') AND expires_at>now()")
  verified=0
  for name,p in cur.fetchall():
   for brief in p.get("_code_issue_briefs") or []:
    if not brief.get("_original_body_excerpt"): continue
    source=next(iter(brief.get("source_articles") or []),None)
    if not source: continue
    details=read_selected_article_details([source],limit=1,with_sources=True)
    if not details: continue
    original=_article_excerpt(details[0].get("text") or "")
    if original and original==brief.get("summary"):
     print("LIVE_ORIGINAL_MATCH",name,"exact_excerpt=True","tags="+str(brief.get("tags") or []),flush=True)
     verified+=1
     break
  print("LIVE_ORIGINAL_MATCH_COUNT",verified,flush=True)
