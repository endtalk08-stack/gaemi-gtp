"""One-time read-only audit of three alternate Naver-listed US close stories.

Uses the existing publisher article reader. No AI, DB, worker changes, deps.
"""
import json,os,re,sys
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.news_detail import read_selected_article_details
ITEMS=[
  {"label":"글로벌이코노믹","url":"https://www.globale.co.kr/news/articleView.html?idxno=41110"},
  {"label":"쿠키뉴스","url":"https://www.kukinews.com/article/view/kuk202610200004"},
  {"label":"뉴스웨이","url":"https://www.newsway.co.kr/news/view?ud=2026102007174135075"},
]
def main():
  print("US3_BACKUP_CHECK_SCOPE=three_alternative_publisher_links_no_AI",flush=True)
  results=read_selected_article_details(ITEMS,limit=3,with_sources=True)
  for item,r in zip(ITEMS,results):
    body=str(r.get("text") or "")
    typ=str(r.get("source") or "")
    accepted=len(body)>=650 and typ in ("jsonld_article_body","article_or_main_paragraphs") and bool(re.search(r"뉴욕증시|나스닥|다우존스|S&P\s*500",body,re.I))
    print("US3_BACKUP="+json.dumps({"label":item["label"],"url":item["url"],
      "source":typ,"body_chars":len(body),"accepted":accepted,
      "excerpt":body[:190]},ensure_ascii=False),flush=True)
  print("US3_BACKUP_COMPLETE",flush=True);return 0
if __name__=="__main__":sys.exit(main())
