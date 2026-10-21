"""Read-only title+description issue extraction proof-of-concept. No price direction, AI, writes, article downloads."""
import os,sys,json,re
sys.path.insert(0,"/opt/gaemigtp-news/app")
import psycopg
DB=os.environ.get("NEWS_DATABASE_URL") or os.environ.get("DATABASE_URL")
assert DB
STOCKS=["삼성전자","SK하이닉스","삼성전기","HT로보틱스","두산에너빌리티","삼성SDI","대한광통신","한화오션"]
EVENTS=[
 ("자사주매입완료",r"자사주.{0,22}(?:매입|취득).{0,40}(?:완료|마무리|종료|끝냈|끝나)|(?:매입|취득).{0,20}(?:완료|종료)", "완료"),
 ("자사주매입계획",r"자사주.{0,22}(?:매입|취득).{0,24}(?:계획|예정|추진|결정)", "예정"),
 ("투자주의지정예고",r"투자주의.{0,18}(?:예고|예정|지정)|투자경고.{0,28}(?:가능성|예고)", "예고"),
 ("목표주가상향",r"목표(?:주)가.{0,32}(?:상향|올렸|높였)|목표.{0,12}(?:상향)", "변경"),
 ("목표주가하향",r"목표(?:주)가.{0,32}(?:하향|내렸|낮췄)", "변경"),
 ("공급계약체결",r"(?:공급계약|납품계약).{0,36}(?:체결|맺었|수주)", "확정"),
 ("업무협약체결",r"(?:업무협약|MOU|전략적.{0,15}파트너십).{0,42}(?:체결|맺었)|(?:체결|맺었).{0,25}(?:업무협약|MOU)", "확정"),
 ("신제품출시",r"(?:신제품|신형|차세대|신규).{0,32}(?:출시|공개|선보)", "발표"),
 ("사업확대",r"(?:사업|시장|사업영역|부품사업).{0,35}(?:확대|넓히|확장)", "진행"),
 ("조직신설",r"(?:조직|팀|사업부|전담조직|코어팀).{0,30}(?:신설|출범)", "확정"),
 ("공장증설",r"(?:공장|생산시설|생산라인).{0,32}(?:증설|확충|첨단화)", "진행"),
 ("실적증가",r"(?:영업이익|순이익|매출).{0,36}(?:증가|급증|성장|최대)", "실적"),
 ("외국인매도",r"외국인.{0,35}(?:순매도|매도세|매도)", "수급"),
 ("대규모수주",r"(?:수주|발주).{0,20}(?:억|조|규모)|(?:억|조).{0,22}(?:수주|발주)", "계약"),
 ("지분인수",r"(?:지분|기업|회사를).{0,26}(?:인수|취득)", "확정"),
]
OTHER_NAMES=["삼성전자","SK하이닉스","삼성전기","HT로보틱스","두산에너빌리티","삼성SDI","대한광통신","한화오션","삼성전자우","포스코DX","LG에너지솔루션","현대차","NAVER"]
def clean(s):
 return re.sub(r"<[^>]+>"," ",str(s or "")).replace("&quot;",'"').replace("&amp;","&").strip()
def relevant(stock,title,desc):
 t=title+" "+desc
 if stock not in t:return False
 # Do not treat similarly named unrelated legal entities as exact owners.
 if re.fullmatch(r"[A-Za-z]{2,5}",stock) and re.search(re.escape(stock)+r"[가-힣]{2,}",t):return False
 if stock not in title:
  subject=re.split(r"[·,，:/…-]",title)[0]
  if any(x in subject for x in OTHER_NAMES if x!=stock):return False
 return True
def evaluate(stock,item):
 title=clean(item.get("title"));desc=clean(item.get("description") or item.get("summary") or item.get("snippet") or "")
 if not title:return {"decision":"PASS","reason":"missing_title","title":title}
 if not relevant(stock,title,desc):return {"decision":"PASS","reason":"not_company_event","title":title}
 sentences=[title]+[s.strip() for s in re.split(r"(?<=[.!?。])\s+|\n+",desc) if len(s.strip())>12]
 hits=[]
 for line in sentences:
  for label,regex,state in EVENTS:
   m=re.search(regex,line,re.I)
   if not m:continue
   if re.search(r"(?:(?:할|될) 경우|가능할|검토 중|아직 미정|사실무근)",line) and state=="확정":continue
   if label=="사업확대":
    match=re.search(r"([가-힣A-Za-z0-9]{2,16})(?:용|의)?\s*(?:핵심)?\s*(?:부품|로봇|반도체)?\s*사업.{0,12}(?:확대|확장|넓히)",line)
    if match:label=match.group(0).replace(" ","")[:25]
   if label not in [a["keyword"] for a in hits]:
    hits.append({"keyword":label,"state":state,"evidence":line[:170]})
 if not hits:return {"decision":"PASS","reason":"no_clear_event","title":title}
 # preserve text-supported headline; never invent a causal market narrative
 return {"decision":"ISSUE_CANDIDATE","title":title,"keywords":hits[:3],"description":desc[:200]}
print("TEST=TITLE_DESCRIPTION_ONLY READ_ONLY NO_AI NO_PRICE NO_BODY_FETCH",flush=True)
total=accepted=0
with psycopg.connect(DB,connect_timeout=12) as conn:
 with conn.cursor() as cur:
  cur.execute("SET TRANSACTION READ ONLY")
  for stock in STOCKS:
   cur.execute("""SELECT a.obj FROM public.news_processed_snapshots s,
       LATERAL jsonb_array_elements(COALESCE(s.result_payload->'paired_news_items','[]'::jsonb))
       WITH ORDINALITY a(obj,ord)
       WHERE s.market='국내' AND s.stock_name=%s ORDER BY a.ord LIMIT 15""",(stock,))
   items=[row[0] for row in cur.fetchall()]
   seen=set();count=0
   for i,item in enumerate(items,1):
    url=item.get("url") or item.get("link") or ""
    if url and url in seen:continue
    seen.add(url)
    result=evaluate(stock,item)
    total+=1
    if result["decision"]=="ISSUE_CANDIDATE":accepted+=1;count+=1
    print("ARTICLE "+json.dumps({"stock":stock,"position":i,**result},ensure_ascii=False),flush=True)
   print("STOCK_SUMMARY "+json.dumps({"stock":stock,"checked":len(items),"accepted":count},ensure_ascii=False),flush=True)
print("FINAL "+json.dumps({"checked":total,"candidates":accepted,"passed":total-accepted},ensure_ascii=False),flush=True)
