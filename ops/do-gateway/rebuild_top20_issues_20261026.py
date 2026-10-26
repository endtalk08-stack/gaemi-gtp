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
  panel=result.get("panel_news_items") or []
  assert len(panel)==len(briefs), "article_hidden"
  print("TOP20_REBUILD",json.dumps({"panel_news":len(panel),"stock":name,"symbol":item["symbol"],"status":"saved","issues":len(briefs),"missing_tags":sum(not b.get("tags") for b in briefs),"original_body_verified":sum(bool(b.get("_original_body_excerpt")) for b in briefs)},ensure_ascii=False),flush=True)
 except Exception as exc:
  print("TOP20_REBUILD",json.dumps({"stock":name,"symbol":item["symbol"],"status":"failed","error":type(exc).__name__},ensure_ascii=False),flush=True)

from backend.services.news_freshness import clean_us_snapshot
from datetime import datetime,timezone
import psycopg
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 conn.execute("SET TRANSACTION READ ONLY")
 with conn.cursor() as cur:
  cur.execute("SELECT stock_name,result_payload FROM public.news_processed_snapshots WHERE market='미국' AND expires_at>now()")
  for name,p in cur.fetchall():
   if p.get("_code_source_revision")!=17: continue
   visible=clean_us_snapshot(p,issue_mode="code")
   issues=visible.get("issue_briefs") or []
   panel=visible.get("panel_news_items") or []
   print("STORED_VISIBILITY",json.dumps({"stock":name,"panel":len(panel),"code":len(issues),"empty_body_visible":sum(not b.get("summary") for b in issues),"missing_keywords_visible":sum(not b.get("tags") for b in issues)},ensure_ascii=False),flush=True)
   for b in issues:
    if name=="엔비디아" and ("휴머노이드" in b.get("headline","") or "휴머노이드공동개발" in (b.get("tags") or [])):
     print("NVIDIA_HUMANOID",json.dumps({"title":b["headline"],"tags":b.get("tags"),"source":b.get("source_articles")},ensure_ascii=False),flush=True)
