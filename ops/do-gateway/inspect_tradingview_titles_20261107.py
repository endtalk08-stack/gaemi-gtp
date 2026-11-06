import json
from collections import defaultdict
from pathlib import Path

page=Path("/var/lib/gaemigtp-news/tradingview-news-page.json")
p=json.loads(page.read_text(encoding="utf-8"))
items=p.get("items",[])

by=defaultdict(list)
for x in items:
    code=(x.get("event_category") or {}).get("code","other")
    by[code].append(x)

for code,rows in sorted(by.items(), key=lambda kv:(-len(kv[1]), kv[0])):
    print("CATEGORY",code,"COUNT",len(rows))
    for x in rows[:12]:
        print("TITLE",code,x.get("published_at",""),"|",x.get("title",""))
    print("---")
