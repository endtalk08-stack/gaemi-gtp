import os,sys,json
sys.path.insert(0,"/opt/gaemigtp-news/app")
import psycopg
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 conn.execute("SET TRANSACTION READ ONLY")
 with conn.cursor() as cur:
  cur.execute("SELECT stock_name,result_payload FROM public.news_processed_snapshots WHERE market='미국' AND stock_name IN ('엔비디아','AMD','루멘텀 홀딩스') AND expires_at>now()")
  for name,p in cur.fetchall():
   for b in (p.get("_code_issue_briefs") or [])[:8]:
    print("EVENT_AUDIT",json.dumps({"stock":name,"title":b.get("headline"),"events":b.get("selected_events")},ensure_ascii=False),flush=True)
   for a in (p.get("panel_news_items") or [])[:8]:
    print("ARTICLE_AUDIT",json.dumps({"stock":name,"title":a.get("title"),"description":a.get("description"),"events":(a.get("event_classification") or {}).get("events")},ensure_ascii=False),flush=True)
