"""Korean issue keyword extraction from stored article titles/descriptions.
No AI, body fetch, price-direction check, or DB access. Change tags only.
"""
import html
import re
from copy import deepcopy

VERB = re.compile(r"매입|취득|완료|종료|첨단화|증설|확충|신설|출범|설립|체결|협력|공급|수주|투자|확대|강화|상향|하향|출시|양산|지정|예고|소각|전환|개발|진출|철수|중단|감산|인수|합병")
ACTIONS = (
 ("자사주매입완료",r"자사주.{0,30}(?:매입|취득).{0,40}(?:완료|종료|마무리|끝냈|끝나)|자사주.{0,30}(?:매입|취득)\\s*조기\\s*완료"),
 ("자사주매입계획",r"자사주.{0,30}(?:매입|취득).{0,20}(?:계획|추진|예정|결정)"),
 ("투자경고지정예고",r"투자경고.{0,25}(?:지정예고|지정.{0,9}예고|가능성)"),
 ("투자주의지정예고",r"투자주의.{0,20}(?:예고|지정 예정|지정예고)"),
 ("목표주가상향",r"목표(?:주가|가).{0,35}(?:상향|올렸|높였)"),
 ("목표주가하향",r"목표(?:주가|가).{0,35}(?:하향|내렸|낮췄)"),
 ("공급계약체결",r"공급\\s*계약.{0,30}(?:체결|맺|수주)"),
 ("협약체결",r"(?:업무협약|MOU|파트너십).{0,45}(?:체결|맺)|(?:체결|맺).{0,35}(?:업무협약|MOU)"),
 ("생산라인증설",r"(?:생산라인|생산시설|전용라인|공장|팹).{0,30}(?:증설|확충|구축)"),
 ("공장첨단화추진",r"(?:공장|생산시설|생산공정|낸드).{0,35}(?:첨단화|첨단 공정 전환)"),
 ("연구개발센터신설",r"(?:연구개발센터|R&D센터|엔지니어링센터|설계거점).{0,25}(?:신설|설립|조성|마련)"),
 ("로봇부품사업확대",r"(?:로봇|로보틱스).{0,35}(?:부품|정밀부품|핵심부품).{0,32}(?:사업|시장).{0,25}(?:확대|확장|넓히)"),
 ("사업확대",r"(?:사업|시장|분야|영역).{0,25}(?:확대|확장|넓히)"),
 ("신제품출시",r"(?:신제품|차세대|신형).{0,40}(?:출시|선보|공개)"),
 ("지분인수",r"(?:지분|기업).{0,30}(?:인수|취득)"),
 ("조직신설",r"(?:전담조직|코어팀|사업부|조직).{0,25}(?:신설|출범|신규 설치)"),
)
HEADLINE_TOPIC = (
 ("자사주", ("자사주매입완료","자사주매입계획")),
 ("공장 증설", ("생산라인증설",)),
 ("공장증설", ("생산라인증설",)),
 ("제휴", ("협약체결","공급계약체결")),
 ("협약", ("협약체결",)),
 ("공급 계약", ("공급계약체결",)),
 ("공급계약", ("공급계약체결",)),
 ("목표주가", ("목표주가상향","목표주가하향")),
 ("사업 확대", ("로봇부품사업확대","사업확대")),
 ("사업확대", ("로봇부품사업확대","사업확대")),
 ("신규 투자", ("생산라인증설","연구개발센터신설")),
 ("연구", ("연구개발센터신설",)),
 ("조직", ("조직신설",)),
 ("투자주의", ("투자주의지정예고",)),
 ("투자경고", ("투자경고지정예고",)),
)
def norm(value):
 return re.sub(r"\\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",str(value or "")))).strip()
def owner_match(stock,title):
 if stock in title:return True
 # Never assume bare '삼성', 'SK', industry/ETF/group mentions identify a corporation.
 return False
def qualified(label,title,desc):
 t=title+" "+desc
 for key,rx in ACTIONS:
  if key!=label:continue
  if re.search(rx,title,re.I):return True
  # Description must express the event in a stock-owned sentence.
  if re.search(rx,desc,re.I) and VERB.search(title):return True
 return False
def choose_tag(label,title,desc):
 t=title+" "+desc
 # Preserve only text-grounded target specifics; do not infer ownership or causality.
 if label=="공장첨단화추진" and "낸드" in t and ("중국" in t or "中" in title):
  return "중국낸드공장첨단화"
 if label=="생산라인증설":
  if "엔비디아" in t and ("AI" in t or "인공지능" in t) and ("기판" in t):
   return "엔비디아AI기판생산라인증설"
  if "세종" in t and "부산" in t:return "세종부산생산라인증설"
 if label=="협약체결":
  if "엔비디아" in t and "기판" in t:return "엔비디아AI기판협력"
  if "LIG" in t and "유도무기" in t:return "LIG유도무기엔진협력"
 if label=="자사주매입완료":
  m=re.search(r"(\\d+(?:[.,]\\d+)?\\s*조\\s*원?)",title)
  if m:return re.sub(r"\\s+","",m.group(1))+"자사주매입완료"
 return label
def tags_only(payload,stock):
 if not isinstance(payload,dict):return payload,0
 out=deepcopy(payload)
 briefs=out.get("issue_briefs") or []
 news=out.get("paired_news_items") or []
 changed=0
 for brief in briefs:
  if not isinstance(brief,dict) or stock not in (brief.get("stock_names") or []):continue
  heading=norm(brief.get("headline"))
  allowed=next((labels for trigger,labels in HEADLINE_TOPIC if trigger in heading),())
  if not allowed:continue
  matches=[]
  for article in (brief.get("source_articles") or news):
   if not isinstance(article,dict):continue
   title=norm(article.get("title"));desc=norm(article.get("description"))
   if not owner_match(stock,title):continue
   for label in allowed:
    if not qualified(label,title,desc):continue
    # Distinguish planned from completed, or retrospective plans.
    if label=="자사주매입계획" and re.search(r"완료|종료|마무리|끝냈|끝나",title+" "+desc):continue
    if label=="자사주매입완료" and re.search(r"종료 임박|완료 예정|종료 예정",title):continue
    if label=="생산라인증설" and re.search(r"첨단화",title) and not re.search(r"증설|확충|구축",title):continue
    matches.append((label,choose_tag(label,title,desc),title))
  if not matches:continue
  # Never promote different event types to the same issue.
  counts={}
  for label,tag,title in matches:
   counts[tag]=counts.get(tag,0)+1
  best=max(counts,key=lambda t:(counts[t],len(t)))
  old=[str(x).lstrip("#") for x in brief.get("tags") or [] if isinstance(x,str)]
  # Only replace the principal generic label. Other context tags remain unchanged.
  if old:
   replacement=[best]+[x for x in old[1:] if x!=best and x!=old[0]]
  else:replacement=[best]
  replacement=list(dict.fromkeys(replacement))[:3]
  if replacement!=brief.get("tags"):
   brief["tags"]=replacement;changed+=1
 return out,changed
