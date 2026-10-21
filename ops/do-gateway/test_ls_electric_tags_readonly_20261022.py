import os,sys,json,psycopg
sys.path.insert(0,"/opt/gaemigtp-news/app/ops")
from staged_issue_tags_only import tags_only, ACTIONS, norm, qualified, owner_match, choose_tag
db=os.environ.get("NEWS_DATABASE_URL") or os.environ.get("DATABASE_URL")
with psycopg.connect(db,connect_timeout=10) as c:
 with c.cursor() as q:
  q.execute("SET TRANSACTION READ ONLY")
  q.execute("""SELECT result_payload,checked_at FROM public.news_processed_snapshots WHERE market='국내' AND stock_name='LS ELECTRIC' ORDER BY checked_at DESC LIMIT 1""")
  row=q.fetchone()
  if not row:print("NO_SNAPSHOT");sys.exit()
  p,checked=row
  new,n=tags_only(p,"LS ELECTRIC")
  print("STOCK_STATUS "+json.dumps({"checked_at":str(checked),"total_news":len(p.get("paired_news_items") or []),"issue_count":len(p.get("issue_briefs") or []),"changed":n},ensure_ascii=False))
  for a,b in zip(p.get("issue_briefs") or [],new.get("issue_briefs") or []):
   print("ISSUE_DIFF "+json.dumps({"headline":a.get("headline"),"summary":str(a.get("summary") or "")[:200],"old_tags":a.get("tags"),"new_tags":b.get("tags")},ensure_ascii=False))
  for i,a in enumerate((p.get("paired_news_items") or [])[:25],1):
   title=norm(a.get("title"));desc=norm(a.get("description"))
   candidates=[choose_tag(label,title,desc) for label,_ in ACTIONS if owner_match("LS ELECTRIC",title) and qualified(label,title,desc)]
   print("ARTICLE "+json.dumps({"rank":i,"title":title[:140],"description":desc[:185],"candidates":list(dict.fromkeys(candidates))},ensure_ascii=False))
