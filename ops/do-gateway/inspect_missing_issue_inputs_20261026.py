"""Repair known ambiguous issue ownership only; no collection, AI or expiry refresh."""
import sys,os,json
from pathlib import Path
sys.path.insert(0,"/opt/gaemigtp-news/app")
import psycopg
from psycopg.types.json import Jsonb
from backend.services.news_identity_registry import resolve_us_news_identity
from backend.services.news_signal_enrichment import select_issue_articles, _evidence_sentence
state=json.loads(Path("/var/lib/gaemigtp-news/rotation.json").read_text())
names=[a["name"] for a in state["cycle"]]
totals={"panel":0,"selected":0,"removed":0,"stocks":0}
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 with conn.cursor() as cur:
  cur.execute("SELECT stock_name,result_payload FROM public.news_processed_snapshots WHERE market='미국' AND stock_name=ANY(%s) AND result_limit=50 AND storyboard_limit=3 AND expires_at>now() FOR UPDATE",(names,))
  for name,p in cur.fetchall():
   if p.get("_issue_selection_revision")!=2: continue
   old=p.get("_code_issue_briefs") or []
   for brief in old:
    for event in brief.get("selected_events") or []:
     sentence=str(event.get("evidence_sentence") or "")
     span=str(event.get("evidence_span") or "")
     start=sentence.find(span) if span else -1
     if start>=0:
      event["evidence_sentence"]=_evidence_sentence(sentence,start,start+len(span))
   new,_=select_issue_articles([],[],name,aliases=resolve_us_news_identity(name)["search_terms"],previous=old)
   if new!=old:
    p["_code_issue_briefs"]=new
    cur.execute("UPDATE public.news_processed_snapshots SET result_payload=%s WHERE market='미국' AND stock_name=%s AND result_limit=50 AND storyboard_limit=3",(Jsonb(p),name))
   panel=len(p.get("panel_news_items") or [])
   print("FINAL_ISSUE_COUNTS",json.dumps({"stock":name,"panel_articles":panel,"selected_issues":len(new),"removed_ambiguous":len(old)-len(new),"ai_translation_enabled":p.get("_translation_enabled")},ensure_ascii=False),flush=True)
   for b in new[:3] if name=="엔비디아" else []:
    print("FINAL_NVDA_ISSUE",json.dumps({"title":b.get("headline"),"tags":b.get("tags"),"summary":b.get("summary"),"id":b.get("issue_id")},ensure_ascii=False),flush=True)
   totals["panel"]+=panel;totals["selected"]+=len(new);totals["removed"]+=len(old)-len(new);totals["stocks"]+=1
print("FINAL_ISSUE_TOTAL",json.dumps(totals),flush=True)
