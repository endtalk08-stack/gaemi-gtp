"""PROTOTYPE ONLY: direction-matched, body-grounded candidate keywords.
Actual 2026-10-21 KR articles; no database mutations/AI/API spending.
These six sample-specific patterns DO NOT represent a general-language extractor.
"""
import re
import sys
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.services.news_detail import read_selected_article_details

records=[
 ("삼성전자","buyback","https://biz.heraldcorp.com/article/10910113?ref=naver"),
 ("삼성전자","india_share","https://www.sedaily.com/article/20104562?ref=naver"),
 ("삼성전자","core_team","https://www.dnews.co.kr/uhtml/view.jsp?idxno=202610212021222360613"),
 ("HT로보틱스","robot_parts","https://www.etoday.co.kr/news/view/2638410"),
 ("HT로보틱스","warning","https://www.topstarnews.net/news/articleView.html?idxno=16254044"),
 ("HT로보틱스","industry_plan","https://www.eroun.net/news/articleView.html?idxno=93095"),
]
items=[dict(name=name,code=code,url=url) for name,code,url in records]
body={}
for start in range(0,len(items),3):
 batch=items[start:start+3]
 for obj,detail in zip(batch,read_selected_article_details(batch,limit=len(batch),with_sources=True)):
  body[obj["code"]]=detail
  print("BODY "+obj["code"]+" source="+str(detail["source"])+" chars="+str(len(detail["text"])),flush=True)

# These are just known article-specific markers to establish whether the
# approach can separate factual direction and completion states at all.
rules=[
 ("buyback","자사주매입종료","down",r"자사주\s*매입.{0,35}(?:마무리|완료|종료|끝냈)|자사주.{0,14}매입.{0,20}종료", "company_or_sector"),
 ("buyback","외국인매도세","down",r"외국인.{0,30}매도세", "market_flow_not_stock_verified"),
 ("india_share","인도스마트폰점유율1위","up",r"인도.{0,90}(?:점유율.{0,60}1위|스마트폰.{0,70}1위)", "company"),
 ("core_team","차세대메모리코어팀가동","up",r"코어팀.{0,28}가동", "company"),
 ("robot_parts","로봇정밀부품사업확대","up",r"로봇용\s*정밀부품.{0,35}(?:사업을\s*확대|사업\s*확대|확대)", "company"),
 ("warning","투자주의종목지정예고","down",r"투자주의종목.{0,15}지정|투자경고종목.{0,40}투자주의종목", "risk_notice"),
]
positives={"삼성전자": {"india_share"},"HT로보틱스":{"robot_parts"}}
all_candidates={}
for stock in ("삼성전자","HT로보틱스"):
 candidates=[]
 for obj in items:
  if obj["name"]!=stock: continue
  detail=body[obj["code"]]
  text=str(detail.get("text") or "")
  quality=detail.get("source") in ("article_or_main_paragraphs","jsonld_article_body")
  if not quality or stock not in text:
   continue
  for code,label,polarity,pattern,ownership in rules:
   if code!=obj["code"]: continue
   match=re.search(pattern,text,flags=re.IGNORECASE)
   if not match: continue
   excerpt=text[max(0,match.start()-30):match.end()+30]
   # The link to the stock is a hypothesis, not proven return attribution.
   candidates.append(dict(keyword=label,polarity=polarity,ownership=ownership,
       evidence=excerpt.replace("\\n"," ")[:145],origin=code))
 all_candidates[stock]=candidates
 for direction in ("up","down"):
  selected=[entry for entry in candidates if entry["polarity"]==direction][:3]
  print("DIRECTION_RESULT "+stock+" "+direction+" keywords="+repr([x["keyword"] for x in selected]),flush=True)
  for entry in selected:
   print("  GROUNDED keyword="+entry["keyword"]+" attribution="+entry["ownership"]+
         " article="+entry["origin"]+" excerpt="+repr(entry["evidence"]),flush=True)

up_s={x["keyword"] for x in all_candidates["삼성전자"] if x["polarity"]=="up"}
dn_s={x["keyword"] for x in all_candidates["삼성전자"] if x["polarity"]=="down"}
up_h={x["keyword"] for x in all_candidates["HT로보틱스"] if x["polarity"]=="up"}
dn_h={x["keyword"] for x in all_candidates["HT로보틱스"] if x["polarity"]=="down"}
assert "인도스마트폰점유율1위" in up_s,up_s
assert "자사주매입종료" in dn_s and "외국인매도세" in dn_s,dn_s
assert "자사주매입종료" not in up_s and "외국인매도세" not in up_s
assert "로봇정밀부품사업확대" in up_h,up_h
assert "투자주의종목지정예고" in dn_h,dn_h
assert "투자주의종목지정예고" not in up_h
assert "차세대메모리코어팀가동" not in up_s # all_page_paragraphs: unverified
print("PROTOTYPE_2_STOCK_2_DIRECTIONS_EVIDENCE_TEST_PASS",flush=True)
print("LIMITATION=sample_specific_rules; not causal_proof; not generalized_keyword_model",flush=True)
