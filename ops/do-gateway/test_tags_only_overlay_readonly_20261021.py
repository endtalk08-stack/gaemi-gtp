"""Conservative Korean issue TAG-ONLY overlay. No data access, no AI and no title edits."""
import re
from copy import deepcopy

RULES=(
("자사주매입완료",r"자사주.{0,12}(?:매입|취득).{0,23}(?:완료|마무리|종료|끝냈|끝나)|(?:매입|취득).{0,13}(?:완료|종료)","자사주"),
("투자경고지정예고",r"투자경고.{0,15}지정.{0,6}(?:예고|가능성)|투자경고.{0,6}지정예고","투자경고"),
("투자주의지정예고",r"투자주의.{0,13}(?:예고|지정될|지정 예정)","투자주의"),
("업무협약체결",r"(?:업무협약|MOU).{0,40}(?:체결|맺었)|(?:체결|맺었).{0,25}(?:업무협약|MOU)","협약"),
("목표주가상향",r"목표.{0,5}주가.{0,22}(?:상향|올렸|높였)","목표"),
("목표주가하향",r"목표.{0,5}주가.{0,22}(?:하향|내렸|낮췄)","목표"),
)
def tags_only(payload,stock):
 out=deepcopy(payload)
 if not isinstance(out,dict):return payload,0
 briefs=out.get("issue_briefs")
 if not isinstance(briefs,list):return out,0
 changed=0
 for issue in briefs:
  if not isinstance(issue,dict):continue
  if stock not in (issue.get("stock_names") or []):continue
  headline=str(issue.get("headline") or "")
  articles=issue.get("source_articles") or []
  # Only use the issue's own publisher sources, never arbitrary news from the stock feed.
  if not articles:continue
  for label,regex,anchor in RULES:
   if anchor not in headline:continue
   matches=[]
   for article in articles:
    if not isinstance(article,dict):continue
    title=str(article.get("title") or "")
    if not title or not re.search(regex,title,re.I):continue
    # Explicitly skip unrelated-company titles; a title that names the target
    # company must not be led by another issuer or merely mention the stock.
    if stock not in title and not (stock=="삼성전자" and re.search(r"삼성[·\\s]",title)):
     continue
    if label=="자사주매입완료" and re.search(r"종료 임박|완료 예정|마무리 전망",title):continue
    matches.append(title)
   if not matches:continue
   old=issue.get("tags") or []
   old=[str(t).lstrip("#") for t in old if isinstance(t,str) and str(t).strip()]
   new=[label]+[t for t in old if t!=label and (anchor in t or t in ("외국인매도","수급부담"))]
   new=["#"+t for t in list(dict.fromkeys(new))[:3]]
   if new!=old and new!=issue.get("tags"):
    issue["tags"]=new;changed+=1
   break
 return out,changed

import os,sys,json
sys.path.insert(0,"/opt/gaemigtp-news/app")
import psycopg
DB=os.environ.get("NEWS_DATABASE_URL") or os.environ.get("DATABASE_URL")
assert DB
print("MODE=READ_ONLY TAGS_ONLY DRY_RUN NO_AI NO_WRITES")
with psycopg.connect(DB,connect_timeout=10) as conn:
 with conn.cursor() as cur:
  cur.execute("SET TRANSACTION READ ONLY")
  cur.execute("""SELECT stock_name,result_payload FROM public.news_processed_snapshots
  WHERE market='국내' AND expires_at>now() ORDER BY checked_at DESC LIMIT 40""")
  total=0
  for stock,payload in cur.fetchall():
   result,count=tags_only(payload,stock)
   orig=(payload or {}).get("issue_briefs") or []
   new=result.get("issue_briefs") or []
   for a,b in zip(orig,new):
    if a.get("tags")==b.get("tags"):continue
    total+=1
    assert a.get("headline")==b.get("headline")
    assert a.get("summary")==b.get("summary")
    print("TAG_CHANGE "+json.dumps({"stock":stock,"headline":a.get("headline"),"before":a.get("tags"),"after":b.get("tags"),"sources":[x.get("title") for x in a.get("source_articles") or []][:2]},ensure_ascii=False),flush=True)
  print("TOTAL_TAG_CHANGES",total,flush=True)
