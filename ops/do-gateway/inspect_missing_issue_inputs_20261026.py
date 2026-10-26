"""Inspect actual missing-stock inputs and grounded keywords. No AI or processed DB writes."""
import sys,json
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.news_feed import fetch_stock_news
from backend.services.news_identity_registry import resolve_us_news_identity
from backend.analysis.news import score_stock_news,build_connected_keyword_test
for name in ["네비우스 그룹","AMD","SK하이닉스(ADR)","블룸 에너지","누 홀딩스","루멘텀 홀딩스","알파벳 A","아이렌"]:
 canonical=resolve_us_news_identity(name)["news_name"]
 raw=fetch_stock_news(name,market="미국",limit=50)
 scored=score_stock_news(raw,canonical)
 classified=build_connected_keyword_test(scored,canonical,max_keywords=3).get("articles",[])
 print("MISSING_INPUT",json.dumps({"stock":name,"canonical":canonical,"collected":len(raw),"scored":len(scored),"direct":sum(x.get("relation_type")=="direct" for x in classified),"keyword_rows":sum(bool(x.get("keywords")) for x in classified)},ensure_ascii=False),flush=True)
 for article,row in list(zip(scored,classified))[:4]:
  print("MISSING_ARTICLE",json.dumps({"stock":name,"title":article.get("title"),"keywords":row.get("keywords"),"owner":row.get("event_owner"),"relation":row.get("relation_type")},ensure_ascii=False),flush=True)
