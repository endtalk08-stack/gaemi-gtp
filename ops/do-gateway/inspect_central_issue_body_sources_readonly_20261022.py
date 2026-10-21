import os,json,psycopg
db=os.getenv("NEWS_DATABASE_URL") or os.getenv("DATABASE_URL")
with psycopg.connect(db,connect_timeout=10) as c:
 with c.cursor() as q:
  q.execute("SET TRANSACTION READ ONLY")
  q.execute("""SELECT stock_name, result_payload FROM public.news_processed_snapshots WHERE market='국내' AND stock_name IN ('삼성전자','SK하이닉스','HT로보틱스') ORDER BY checked_at DESC LIMIT 15""")
  seen=set()
  for name,p in q.fetchall():
   if name in seen:continue
   seen.add(name)
   for i,b in enumerate((p.get("issue_briefs") or [])[:3]):
    text=str(b.get("summary") or "")
    news=p.get("paired_news_items") or []
    matches=[a for a in news if text and (text[:65] in str(a.get("description") or "") or text[:65] in str(a.get("title") or ""))]
    print("BRIEF "+json.dumps({"stock":name,"index":i,"headline":b.get("headline"),"summary_chars":len(text),"summary_preview":text[:270],"evidence_source":b.get("evidence_source"),"summary_matches_feed_snippet":bool(matches),"keys":list(b.keys())},ensure_ascii=False),flush=True)
