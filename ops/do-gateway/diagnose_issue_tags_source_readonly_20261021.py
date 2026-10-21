import sys,os,json,psycopg
db=os.environ.get("NEWS_DATABASE_URL") or os.environ.get("DATABASE_URL")
with psycopg.connect(db,connect_timeout=10) as c:
 with c.cursor() as q:
  q.execute("SET TRANSACTION READ ONLY")
  q.execute("""SELECT stock_name,result_payload FROM public.news_processed_snapshots WHERE market='국내' AND expires_at>now() ORDER BY checked_at DESC LIMIT 20""")
  for stock,p in q.fetchall():
   b=p.get("issue_briefs") or []
   print("STOCK",json.dumps({"name":stock,"briefs":len(b),"news":len(p.get("paired_news_items") or [])},ensure_ascii=False))
   for x in b[:2]:
    print("BRIEF",json.dumps({"headline":x.get("headline"),"tags":x.get("tags"),"source_count":len(x.get("source_articles") or []),"sources":[t.get("title") for t in x.get("source_articles") or []][:2],"keys":list(x.keys())},ensure_ascii=False))
