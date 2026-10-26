"""User-requested verification of actual displayed issue titles and cited article titles."""
import os,json,psycopg
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 conn.execute("SET TRANSACTION READ ONLY")
 with conn.cursor() as cur:
  cur.execute("SELECT stock_name,result_payload FROM public.news_processed_snapshots WHERE market='미국' AND expires_at>now()")
  for name,p in cur.fetchall():
   for b in p.get("_code_issue_briefs") or []:
    print("ACTUAL_TITLE",json.dumps({"stock":name,"headline":b.get("headline"),"tags":b.get("tags"),"source_titles":[s.get("title") for s in b.get("source_articles") or [] if isinstance(s,dict)]},ensure_ascii=False),flush=True)
