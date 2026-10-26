"""Rebuild currently ranked US listings with selected issues; preserve raw panel."""
import sys,json,os
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services import news_feed,news_processed_store as store
from backend.services.news_result import build_stock_news_result
state=json.loads(Path("/var/lib/gaemigtp-news/rotation.json").read_text())
params=dict(market="미국",limit=50,storyboard_limit=3,display_timezone="Asia/Seoul")
failed=0
for item in list(state["cycle"]):
 name=item["name"]
 try:
  raw=news_feed.fetch_stock_news(name,market="미국",limit=50,raise_on_error=True)
  result=build_stock_news_result(name,raw_news_list=raw,**params)
  assert result.get("_news_status")=="ok", "analysis_failed"
  assert result.get("_issue_selection_revision")==1, "selection_not_deployed"
  issues=result.get("issue_briefs") or []
  assert all(b.get("issue_id") and b.get("selected_events") and b.get("_issue_expires_at") for b in issues)
  assert all(b.get("tags") for b in issues)
  store.save_snapshot(name,fingerprint=store.source_fingerprint(raw),result=result,**params)
  print("SELECTED_24H",json.dumps({"stock":name,"symbol":item["symbol"],"panel_articles":len(result.get("panel_news_items") or []),"selected_issues":len(issues),"rejected_articles":len(result.get("_issue_selection_rejections") or []),"translation_pending":result.get("_translation_pending_count")},ensure_ascii=False),flush=True)
  if item["symbol"] in ("NVDA","NU","LITE"):
   for b in issues[:4]:
    print("SELECTED_SAMPLE",json.dumps({"stock":name,"title":b["headline"],"tags":b["tags"],"id":b["issue_id"],"anchor":b["reaction_anchor_at"],"expires":b["_issue_expires_at"]},ensure_ascii=False),flush=True)
 except Exception as exc:
  failed+=1
  print("SELECTED_FAILED",json.dumps({"stock":name,"error":type(exc).__name__},ensure_ascii=False),flush=True)
print("SELECTED_REBUILD_COMPLETE",json.dumps({"stocks":len(state["cycle"]),"failed":failed}),flush=True)
if failed: raise RuntimeError("some_stock_rebuilds_failed")
