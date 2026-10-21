"""Independent LS ELECTRIC issue keywords solely from news title+description, no existing issue fields."""
import os,re,json,html,psycopg
def norm(x):return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",str(x or "")))).strip()
def extract(title,desc):
 t=title+" "+desc
 tags=[]
 def add(x):
  if x not in tags:tags.append(x)
 if re.search(r"(?:100|백)\s*분기\s*연속\s*(?:영업)?\s*흑자",t):add("100분기연속흑자")
 if re.search(r"(?:3분기|3Q|3분기 연결).{0,55}(?:사상|역대|분기).{0,14}(?:최대|최고)\s*실적|(?:사상|역대|분기)\s*최대\s*실적",t,re.I):add("3분기사상최대실적" if re.search(r"3분기|3Q",t,re.I) else "사상최대실적")
 m=re.search(r"(?:3분기|3Q).{0,85}?영업\s*이익\s*([\d,]+)\s*(억|조)\s*원?",t,re.I)
 if not m:m=re.search(r"영업\s*이익\s*([\d,]+)\s*(억|조)\s*원?",t,re.I)
 if m:add("영업이익"+m.group(1).replace(",","")+m.group(2))
 if re.search(r"(?:북미|미국).{0,80}(?:배전반|변압기|전력기기|수배전반).{0,45}(?:공급|확대|확충)|(?:북미|미국).{0,80}(?:공급|확대).{0,45}(?:배전반|변압기|전력기기)",t):add("북미전력기기공급확대")
 m=re.search(r"([\d,]+)\s*억(?:원)?\s*규모.{0,28}?(?:수배전반|배전반|변압기).{0,28}?(?:공급계약|계약|공급)",t)
 if not m:m=re.search(r"([\d,]+)\s*억(?:원)?\s*규모의?\s*(?:수배전반|배전반).{0,25}?공급계약",t)
 if m and re.search(r"체결|맺었|계약",t):add(m.group(1).replace(",","")+"억수배전반공급계약")
 return tags
db=os.environ.get("NEWS_DATABASE_URL") or os.environ.get("DATABASE_URL")
with psycopg.connect(db,connect_timeout=10) as conn:
 with conn.cursor() as cur:
  cur.execute("SET TRANSACTION READ ONLY")
  cur.execute("""SELECT result_payload->'paired_news_items' FROM public.news_processed_snapshots WHERE market='국내' AND stock_name='LS ELECTRIC' ORDER BY checked_at DESC LIMIT 1""")
  row=cur.fetchone()
  items=row[0] if row and isinstance(row[0],list) else []
  print("MODE=INDEPENDENT_TITLE_DESCRIPTION_ONLY NO_EXISTING_ISSUE_FIELDS NO_AI NO_DB_WRITE",flush=True)
  accepted=0
  for i,item in enumerate(items[:30],1):
   title=norm(item.get("title"));desc=norm(item.get("description"))
   tags=extract(title,desc) if "LS ELECTRIC" in title or "LS일렉" in title else []
   if tags:accepted+=1
   print("ARTICLE "+json.dumps({"rank":i,"title":title[:105],"keywords":tags,"decision":"CANDIDATE" if tags else "PASS"},ensure_ascii=False),flush=True)
  print("RESULT "+json.dumps({"checked":min(30,len(items)),"accepted":accepted},ensure_ascii=False),flush=True)
