"""Independent NVDA title+description-only keyword test. Never uses old issues, AI, prices or full article body."""
import os,re,html,json,psycopg
def norm(x):return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",str(x or "")))).strip()
def extract(title,desc):
 s=title+" "+desc
 out=[]
 def add(k): 
  if k not in out:out.append(k)
 patterns=[
 ("실적발표",r"earnings (?:report|results)|reports? (?:quarterly|q[1-4])|실적\s*발표|분기\s*실적"),
 ("매출증가",r"revenue (?:rose|grew|increased|surged)|sales (?:rose|grew|increased)|매출.{0,15}(?:증가|급증|성장)"),
 ("매출전망상향",r"(?:raise[ds]?|hike[ds]?|boost[sd]?) (?:its )?(?:revenue|sales) (?:guidance|forecast|outlook)|매출.{0,16}(?:전망|가이던스).{0,12}상향"),
 ("실적전망하향",r"(?:cut|lower|reduc)(?:s|es|ed|ing)? .{0,32}(?:guidance|forecast|outlook)|실적.{0,18}(?:전망|가이던스).{0,12}하향"),
 ("신제품공개",r"(?:unveil|announce|introduc)(?:s|es|ed|ing)? .{0,40}(?:GPU|chip|processor|platform)|(?:GPU|칩|반도체).{0,22}(?:공개|발표|출시)"),
 ("신제품출시",r"(?:launch|releas|ship)(?:es|ed|ing|s)? .{0,48}(?:GPU|chip|processor|platform)|(?:GPU|칩|반도체).{0,22}(?:출시|양산)"),
 ("AI칩공급계약",r"(?:supply|sells?|provides?) .{0,40}(?:AI chips?|GPUs?).{0,32}(?:deal|contract|agreement)|(?:AI칩|GPU).{0,27}(?:공급계약|납품계약)"),
 ("파트너십체결",r"(?:sign|signs|signed|strike|strikes|struck|announce|announces|announced) .{0,35}(?:partnership|agreement)|(?:파트너십|업무협약|협력계약).{0,30}(?:체결|발표)"),
 ("수출규제강화",r"(?:export restriction|export control|chip export ban|수출규제).{0,40}(?:tighten|expand|강화|확대)|(?:tighten|expand).{0,35}(?:export restriction|export control)"),
 ("주가목표상향",r"(?:raise|raises|raised|hike|hikes|hiked) .{0,30}price target|(?:price target).{0,30}(?:raised|higher|hiked)|목표주가.{0,25}(?:상향|인상)"),
 ("주가목표하향",r"(?:cut|cuts|lower|lowers|lowered) .{0,30}price target|price target.{0,30}(?:cut|lowered)|목표주가.{0,25}(?:하향|인하)"),
 ("투자확대",r"(?:invest|investment).{0,40}(?:billion|million|expanded|increase)|(?:투자).{0,28}(?:확대|증액)"),
 ]
 for key,rx in patterns:
  if re.search(rx,title,re.I) or (re.search(rx,desc,re.I) and re.search(r"NVIDIA|엔비디아|NVDA",desc,re.I)):add(key)
 # Add numeric revenue only if explicitly labelled revenue in same sentence.
 m=re.search(r"(?:revenue|매출)(?:\s+(?:of|was|hit|reached|at))?\s*[:=]?\s*\$?([\d,.]+)\s*(billion|million|억|조)",s,re.I)
 if m:add("매출"+m.group(1).replace(",","")+({"billion":"십억달러","million":"백만달러"}.get(m.group(2).lower(),m.group(2))))
 return out
db=os.getenv("NEWS_DATABASE_URL") or os.getenv("DATABASE_URL")
with psycopg.connect(db,connect_timeout=10) as conn:
 with conn.cursor() as cur:
  cur.execute("SET TRANSACTION READ ONLY")
  cur.execute("""SELECT stock_name, result_payload, checked_at FROM public.news_processed_snapshots WHERE market IN ('미국','US') AND (stock_name ILIKE '%NVIDIA%' OR stock_name ILIKE '%NVDA%' OR stock_name LIKE '%엔비디아%') ORDER BY checked_at DESC LIMIT 5""")
  rows=cur.fetchall()
  print("MODE=READ_ONLY_NVDA_TITLE_DESCRIPTION_ONLY NO_AI NO_EXISTING_TAGS NO_PRICE",flush=True)
  for stock,p,checked in rows:
   news=p.get("paired_news_items") or p.get("news_items") or []
   print("STOCK "+json.dumps({"stock":stock,"checked":str(checked),"total_news":len(news),"keys":list(p.keys())[:25]},ensure_ascii=False),flush=True)
   n=0
   for i,a in enumerate(news[:35],1):
    t=norm(a.get("title"));d=norm(a.get("description") or a.get("summary") or a.get("snippet"))
    if not t:continue
    tags=extract(t,d) if re.search(r"NVIDIA|엔비디아|NVDA",t+" "+d,re.I) else []
    if tags:n+=1
    print("ARTICLE "+json.dumps({"rank":i,"title":t[:140],"description":d[:170],"keywords":tags,"decision":"CANDIDATE" if tags else "PASS"},ensure_ascii=False),flush=True)
   print("RESULT "+json.dumps({"stock":stock,"checked":min(len(news),35),"accepted":n},ensure_ascii=False),flush=True)
  if not rows:print("NO_NVDA_SNAPSHOT",flush=True)
