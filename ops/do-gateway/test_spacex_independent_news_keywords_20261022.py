"""SpaceX independent news title+description extraction test. No AI or stored issues."""
import os,re,html,json,psycopg
def norm(x):return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",str(x or "")))).strip()
def extract(title,description):
 text=title+" "+description
 tags=[]
 def add(label):
  if label not in tags:tags.append(label)
 rules=[
 ("로켓발사성공",r"(?:SpaceX|스페이스X).{0,90}(?:launch(?:ed|es)? successfully|successful launch|발사 성공)|(?:팰컨|스타십|Starship|Falcon).{0,45}(?:launch(?:ed|es)? successfully|발사 성공)"),
 ("로켓발사예정",r"(?:SpaceX|스페이스X|Starship|Falcon|스타십|팰컨).{0,75}(?:발사 예정|발사 계획|발사 추진|scheduled to launch|plans to launch|launch scheduled)"),
 ("스타십시험비행",r"(?:스타십|Starship).{0,50}(?:시험비행|시험 비행|test flight|flight test)"),
 ("스타십발사성공",r"(?:스타십|Starship).{0,50}(?:발사 성공|successful launch)"),
 ("스타십발사실패",r"(?:스타십|Starship).{0,60}(?:발사 실패|폭발|추락|explod(?:e|ed|es)|launch fail)"),
 ("위성발사",r"(?:스타링크|Starlink).{0,60}(?:위성.{0,12}발사|satellites?.{0,20}launch)|(?:SpaceX|스페이스X).{0,60}(?:satellite launch|위성 발사)"),
 ("스타링크서비스확대",r"(?:스타링크|Starlink).{0,75}(?:서비스 확대|서비스 개시|서비스 출시|서비스 진출|expands? service|launches? service)"),
 ("스페이스X기업공개추진",r"(?:SpaceX|스페이스X).{0,75}(?:IPO|기업공개|상장 추진|상장 계획|go public)|(?:IPO|기업공개).{0,35}(?:SpaceX|스페이스X)"),
 ("스페이스X기업가치평가",r"(?:SpaceX|스페이스X).{0,65}(?:기업가치|valuation|가치평가)"),
 ("스페이스X합병논의",r"(?:SpaceX|스페이스X).{0,75}(?:합병|merger|merge)|(?:합병|merger).{0,40}(?:SpaceX|스페이스X)"),
 ("우주선착륙성공",r"(?:스타십|Starship|팰컨|Falcon).{0,65}(?:착륙 성공|successfully landed|successful landing)"),
 ("우주선발사계약",r"(?:SpaceX|스페이스X).{0,75}(?:발사 계약|launch contract|launch agreement)"),
 ]
 for label,rx in rules:
  if re.search(rx,title,re.I) or re.search(rx,description,re.I):add(label)
 return tags
db=os.getenv("NEWS_DATABASE_URL") or os.getenv("DATABASE_URL")
with psycopg.connect(db,connect_timeout=10) as conn:
 with conn.cursor() as cur:
  cur.execute("SET TRANSACTION READ ONLY")
  cur.execute("""SELECT stock_name, result_payload, checked_at FROM public.news_processed_snapshots WHERE market IN ('미국','US') AND (stock_name ILIKE '%space%' OR stock_name ILIKE '%스페이스%' OR stock_name ILIKE '%SPX%') ORDER BY checked_at DESC LIMIT 5""")
  rows=cur.fetchall()
  print("MODE=SPACE_X READ_ONLY TITLE_DESCRIPTION_ONLY NO_OLD_KEYWORDS NO_OLD_ISSUES NO_AI",flush=True)
  if not rows:print("NO_SPACE_X_SNAPSHOT",flush=True)
  for stock,p,checked in rows:
   news=p.get("paired_news_items") or p.get("panel_news_items") or []
   print("STOCK "+json.dumps({"stock":stock,"checked_at":str(checked),"total_stored":len(news)},ensure_ascii=False),flush=True)
   accepted=0
   for i,item in enumerate(news[:35],1):
    title=norm(item.get("title"));desc=norm(item.get("description") or item.get("summary") or item.get("snippet"))
    tags=extract(title,desc) if re.search(r"SpaceX|스페이스\s?X|스타십|Starship|스타링크|Starlink",title+" "+desc,re.I) else []
    if tags:accepted+=1
    print("ARTICLE "+json.dumps({"rank":i,"title":title[:155],"description":desc[:150],"tags":tags,"decision":"CANDIDATE" if tags else "PASS"},ensure_ascii=False),flush=True)
   print("RESULT "+json.dumps({"checked":min(35,len(news)),"accepted_articles":accepted},ensure_ascii=False),flush=True)
