import os,json,psycopg,hashlib
from backend.services.shared_v1_issue_titles import extract
from backend.services.news_result import get_shared_stock_news_result
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
   try:
    result=get_shared_stock_news_result(stock,market=market)
    print("READ_API "+json.dumps({"stock":stock,"status":result.get("_news_status"),"issue_count":len(result.get("issue_briefs") or []),"first_headline":(result.get("issue_briefs") or [{}])[0].get("headline")},ensure_ascii=False),flush=True)
   except Exception as exc:print("READ_API_ERROR="+stock+" "+type(exc).__name__,flush=True)
