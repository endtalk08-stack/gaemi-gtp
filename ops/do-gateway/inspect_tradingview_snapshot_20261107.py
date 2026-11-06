import json
from collections import Counter
from pathlib import Path

bundle=Path("/var/lib/gaemigtp-news/tradingview-news-bundle.json")
page=Path("/var/lib/gaemigtp-news/tradingview-news-page.json")

b=json.loads(bundle.read_text(encoding="utf-8"))
p=json.loads(page.read_text(encoding="utf-8"))

print("BUNDLE_ITEMS", len(b.get("items",[])))
print("BUNDLE_OK_CATEGORIES", b.get("ok_categories"))
print("BUNDLE_FAILED_CATEGORIES", b.get("failed_categories"))
print("BUNDLE_REQUESTS_LAST_REFRESH", b.get("requests_last_refresh"))
print("BUNDLE_REQUESTS_TOTAL", b.get("requests_total"))

source_counts=Counter()
for x in b.get("items",[]):
    for c in x.get("news_categories") or []:
        source_counts[c]+=1
print("BUNDLE_SOURCE_COUNTS", dict(source_counts))

items=p.get("items",[])
print("PAGE_ITEMS", len(items))
print("PAGE_CATEGORY_COUNTS", p.get("category_counts",{}))
print("PAGE_SECTION_COUNTS", dict(Counter(x.get("news_section") for x in items)))

for section in ("stock","market"):
    rows=[x for x in items if x.get("news_section")==section][:8]
    print("SAMPLE_SECTION",section,"COUNT",len(rows))
    for x in rows:
        print("SAMPLE",section,x.get("event_category"),x.get("title")[:180])
