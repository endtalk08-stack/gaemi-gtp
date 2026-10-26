"""Read-only code-analysis diagnosis. No AI calls and no processed snapshot writes."""
import sys,json
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.news_identity_registry import resolve_us_news_identity
from backend.services.news_feed import fetch_stock_news
from backend.analysis.news import score_stock_news,build_connected_keyword_test
from backend.services.news_result import build_stock_news_result
for name in ["메타 플랫폼스(페이스북)","팔란티어 테크","알파벳 A","아마존닷컴"]:
 identity=resolve_us_news_identity(name)
 raw=fetch_stock_news(name,limit=50,market="미국",raise_on_error=True)
 canonical=identity["news_name"]
 scored=score_stock_news(raw,canonical)
 classified=build_connected_keyword_test(scored,canonical,max_keywords=3).get("articles",[])
 relations={}
 for row in classified:
  key=row.get("relation_type","unknown")
  relations[key]=relations.get(key,0)+1
 print("CODE_INPUT_DIAG",json.dumps({"stock":name,"canonical":canonical,"collected":len(raw),"scored":len(scored),"relations":relations},ensure_ascii=False),flush=True)
 result=build_stock_news_result(name,market="미국",limit=50,storyboard_limit=3,display_timezone="Asia/Seoul",raw_news_list=raw)
 print("CODE_RESULT_DIAG",json.dumps({"stock":name,"status":result.get("_news_status"),"paired":len(result.get("paired_news_items") or []),"selected":len(result.get("storyboard_news_items") or []),"issues":len(result.get("issue_briefs") or [])},ensure_ascii=False),flush=True)
