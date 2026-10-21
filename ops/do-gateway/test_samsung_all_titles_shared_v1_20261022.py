"""Fixed shared extractor v1: no stock-specific rules and no legacy tags."""
import os,re,html,json,hashlib,psycopg
STOCKS=("엔비디아","스페이스X")
def clean(s):
 s=html.unescape(re.sub(r"<[^>]*>"," ",str(s or "")))
 return re.sub(r"\s+"," ",s).strip()
def normalize(s):
 return re.sub(r"[^가-힣a-z0-9]","",s.lower())
def extract(title,description):
 text=clean(title+" "+description)
 # Same reusable language-agnostic phrase extraction for all companies.
 # Select spans bounded by event verbs, preserving adjacent topic words/numbers.
 action=r"(?:발표|공개|개발|출시|공급|구축|투자|협력|확대|강화|전환|인수|합병|검토|추진|체결|실적|흑자|증가|감소|상승|하락|조정|단축|유지|기록|돌파|달성|예정|확정|승인|배포|중단|착수|보고|매출|이익|launch|launches|launched|release|released|report|reported|reports|announc\w*|merg\w*|invest\w*|partnership|revenue|earnings|profit|growth|develop\w*|expand\w*|deploy\w*|unveil\w*|supply|contract|agreement)"
 chunks=re.split(r"(?<=[.!?])\s+|[;｜|]|…",text)
 terms=[]
 for chunk in chunks:
  for match in re.finditer(action,chunk,re.I):
   # Tight context near each described event, never pure topic whitelist.
   left=chunk[max(0,match.start()-42):match.start()]
   right=chunk[match.end():match.end()+18]
   phrase=(left+match.group()+right).strip(" ,.:\t\n")
   phrase=re.sub(r"\s+"," ",phrase)
   if len(phrase)>85: phrase=phrase[-85:]
   if len(phrase)<6:continue
   terms.append(phrase)
 # Prefer title event wording, then description facts; maximum 3 displayed.
 results=[]
 for term in terms:
  key=normalize(term)
  if key and not any(key in normalize(prev) or normalize(prev) in key for prev in results):
   results.append(term)
  if len(results)>=3:break
 return results

DB=os.getenv("NEWS_DATABASE_URL") or os.getenv("DATABASE_URL")
print("EXTRACTOR_SHA256="+hashlib.sha256(extract.__code__.co_code).hexdigest(),flush=True)
with psycopg.connect(DB,connect_timeout=10) as conn:
 with conn.cursor() as cur:
  cur.execute("SET TRANSACTION READ ONLY")
  cur.execute("""SELECT result_payload,checked_at FROM public.news_processed_snapshots WHERE market='국내' AND stock_name=%s ORDER BY checked_at DESC LIMIT 1""",("삼성전자",))
  row=cur.fetchone()
  if not row: print("MISSING_STOCK=삼성전자",flush=True)
  else:
   p,checked=row;news=p.get("paired_news_items") or []
   print("INFO "+json.dumps({"stock":"삼성전자","checked":str(checked),"total_news":len(news)},ensure_ascii=False),flush=True)
   out=[]
   for i,item in enumerate(news,1):
    title=clean(item.get("title"));desc=clean(item.get("description"))
    phrases=extract(title,desc)
    for phrase in phrases:
     out.append({"rank":i,"time":item.get("published_at") or item.get("pubDate") or item.get("time"),"extracted_title":phrase,"article_title":title[:105]})
   print("COUNT="+str(len(out)),flush=True)
   for x in sorted(out,key=lambda a:str(a["time"] or "")):print("ISSUE "+json.dumps(x,ensure_ascii=False),flush=True)
