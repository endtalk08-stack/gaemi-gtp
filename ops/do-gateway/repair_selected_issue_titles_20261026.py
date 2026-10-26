"""Repair only selected issue headlines from their own existing cited Korean article titles."""
import os,re,json,psycopg
from psycopg.types.json import Jsonb
changed=0
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 with conn.cursor() as cur:
  cur.execute("SELECT stock_name,result_limit,storyboard_limit,display_timezone,result_payload FROM public.news_processed_snapshots WHERE market='미국' AND expires_at>now() FOR UPDATE")
  for name,limit,story,tz,p in cur.fetchall():
   count=0
   for key in ("_code_issue_briefs","issue_briefs"):
    for b in p.get(key) or []:
     if not isinstance(b,dict): continue
     title=next((str(s.get("title") or "").strip() for s in b.get("source_articles") or [] if isinstance(s,dict) and re.search("[가-힣]",str(s.get("title") or ""))),"")
     if title and b.get("headline")!=title:
      b["headline"]=title
      count+=1
   if count:
    cur.execute("UPDATE public.news_processed_snapshots SET result_payload=%s WHERE market='미국' AND stock_name=%s AND result_limit=%s AND storyboard_limit=%s AND display_timezone=%s",(Jsonb(p),name,limit,story,tz))
    changed+=count
    print("TITLE_REPAIRED",name,count,flush=True)
print("TITLE_REPAIR_TOTAL",changed,flush=True)
