"""Read-only count of currently visible 24-hour US code news. No API/AI calls."""
import sys,os,json
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
sys.path.insert(0,"/opt/gaemigtp-news/app")
import psycopg
now=datetime.now(timezone.utc)
cutoff=now-timedelta(hours=24)
def fresh(source):
 try:
  v=str(source.get("published_at") or "")
  try: d=datetime.fromisoformat(v.replace("Z","+00:00"))
  except ValueError: d=parsedate_to_datetime(v)
  return d.tzinfo is not None and cutoff<=d.astimezone(timezone.utc)<=now and str(source.get("url") or "").startswith(("http://","https://"))
 except Exception: return False
state=json.loads(Path("/var/lib/gaemigtp-news/rotation.json").read_text())
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 conn.execute("SET TRANSACTION READ ONLY")
 with conn.cursor() as cur:
  cur.execute("SELECT stock_name,result_payload,processed_at,expires_at FROM public.news_processed_snapshots WHERE market='미국' AND result_limit=50 AND storyboard_limit=3 AND display_timezone='Asia/Seoul'")
  saved={name:(p,processed,expiry) for name,p,processed,expiry in cur.fetchall()}
  total=tagged=0
  print("COUNT_ASOF",now.isoformat(),flush=True)
  for item in state["cycle"]:
   name=item["name"]; row=saved.get(name)
   p,processed,expiry=row if row else ({},None,None)
   valid=bool(expiry and expiry>now)
   compatible=str(p.get("_title_only_revision"))=="3" and str(p.get("_code_fact_extraction_version"))=="3"
   briefs=[b for b in p.get("_code_issue_briefs",[]) if isinstance(b,dict) and any(fresh(s) for s in b.get("source_articles",[]) if isinstance(s,dict))] if valid and compatible else []
   withtags=sum(bool(b.get("tags")) for b in briefs)
   total+=len(briefs);tagged+=withtags
   print("CURRENT_24H_COUNT",json.dumps({"stock":name,"symbol":item["symbol"],"visible_articles":len(briefs),"with_keywords":withtags,"without_keywords":len(briefs)-withtags,"classified_events":sum(bool(b.get("event_types")) for b in briefs),"taxonomy_version":p.get("_event_taxonomy_revision"),"processed_at":str(processed),"snapshot_valid":valid},ensure_ascii=False),flush=True)
  print("CURRENT_24H_TOTAL",json.dumps({"articles":total,"with_keywords":tagged,"without_keywords":total-tagged}),flush=True)
