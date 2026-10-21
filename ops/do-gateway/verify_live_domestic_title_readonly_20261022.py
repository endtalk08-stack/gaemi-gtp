import sys
sys.path.insert(0,'/opt/gaemigtp-news/app')
import os,json,psycopg,hashlib
from backend.services.shared_v1_issue_titles import extract
import pathlib
base=pathlib.Path('/opt/gaemigtp-news/app/backend/services')
print('SERVER_MODULES '+json.dumps({x:(base/x).exists() for x in ['news_result.py','news_byline.py','issue_briefs.py','shared_v1_issue_titles.py']},ensure_ascii=False),flush=True)
print("EXTRACTOR_SHA256="+hashlib.sha256(extract.__code__.co_code).hexdigest(),flush=True)
db=os.getenv("NEWS_DATABASE_URL") or os.getenv("DATABASE_URL")
with psycopg.connect(db,connect_timeout=10) as c:
 with c.cursor() as q:
  q.execute("SET TRANSACTION READ ONLY")
  for market,stock in (("국내","삼성전자"),("국내","SK하이닉스"),("미국","엔비디아")):
   q.execute("SELECT checked_at,result_payload FROM public.news_processed_snapshots WHERE market=%s AND stock_name=%s ORDER BY checked_at DESC LIMIT 1",(market,stock))
   row=q.fetchone()
   if not row:print("MISSING "+stock,flush=True);continue
   checked,p=row
   briefs=p.get("issue_briefs") or []
   news=p.get("storyboard_news_items") or []
   print("SNAPSHOT "+json.dumps({"market":market,"stock":stock,"checked":str(checked),"issue_count":len(briefs),"selected_articles":len(news)},ensure_ascii=False),flush=True)
   for i,b in enumerate(briefs[:5]):
    matching=extract(str(news[i].get("title") or ""),str(news[i].get("description") or "")) if i<len(news) else []
    print("ISSUE "+json.dumps({"stock":stock,"headline":b.get("headline"),"extract":matching[:1],"summary_chars":len(str(b.get("summary") or "")),"tags":b.get("tags"),"headline_matches":bool(matching and b.get("headline")==matching[0])},ensure_ascii=False),flush=True)

