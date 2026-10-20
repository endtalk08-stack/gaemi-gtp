"""Read-only single-run review of existing article-body extractor on three Naver-returned publisher links.

No new packages, keys, DB, AI, services, or UI modifications. Output only
download/extraction labels and lengths; no full publisher texts.
"""
import importlib.util
import json
import sys

from backend.services.news_detail import read_selected_article_details

ITEMS = [
    {"url": "https://www.hankyung.com/article/2026102040051",
     "label": "Hankyung (Oct20 source)"},
    {"url": "https://www.polinews.co.kr/news/articleView.html?idxno=746328",
     "label": "Polinews (Oct20 source)"},
    {"url": "https://www.newsis.com/view/NISX20261020_0003833863",
     "label": "Newsis (Oct20 source)"},
]

def main():
    print("ARTICLE_EXTRACT_AUDIT_SCOPE=three_fixed_publisher_urls_only", flush=True)
    print("TRAFILATURA_ALREADY_INSTALLED="+str(importlib.util.find_spec("trafilatura") is not None).lower(), flush=True)
    details=read_selected_article_details(ITEMS,limit=3,with_sources=True)
    for item,detail in zip(ITEMS,details):
        body=str(detail.get("text") or "")
        source=str(detail.get("source") or "fetch_failed")
        # Scoring threshold here is merely exploratory, not guarantee of correct body.
        qualified=len(body)>=500 and source not in ("fetch_failed","meta_description")
        print("ARTICLE_EXTRACT_AUDIT_RESULT="+json.dumps({
            "label":item["label"],"source":source,
            "chars":len(body),"words":len(body.split()),
            "looks_like_body":qualified,
        },ensure_ascii=False),flush=True)
    print("ARTICLE_EXTRACT_AUDIT_COMPLETED",flush=True)
    return 0

if __name__=="__main__":
    sys.exit(main())
