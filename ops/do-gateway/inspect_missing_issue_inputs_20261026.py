import sys,os,json
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.news_identity_registry import resolve_us_news_identity
import psycopg
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 conn.execute("SET TRANSACTION READ ONLY")
 with conn.cursor() as cur:
  cur.execute("SELECT stock_name,result_payload FROM public.news_processed_snapshots WHERE market='미국' AND stock_name IN ('엔비디아','누 홀딩스') AND expires_at>now()")
  for name,p in cur.fetchall():
   print("IDENTITY",json.dumps(resolve_us_news_identity(name),ensure_ascii=False),flush=True)
   articles={a.get("url") or a.get("link"):a for a in p.get("panel_news_items") or []}
   for brief in p.get("_code_issue_briefs") or []:
    if brief.get("tags"): continue
    url=(brief.get("source_articles") or [{}])[0].get("url")
    a=articles.get(url,{})
    print("MISSING_KEYWORD",json.dumps({"stock":name,"title":brief.get("headline"),"description":a.get("description"),"summary":brief.get("summary")},ensure_ascii=False),flush=True)
