"""Read only NVDA collection JSON metadata; no DB, external calls or secret output."""
import json
from pathlib import Path
from urllib.parse import urlsplit
p=Path("/run/gaemi-gateway/nvda-news-test-20261028.json")
if not p.is_file() or p.is_symlink():
    raise SystemExit("NVDA_READ_ERROR=json_missing")
data=json.loads(p.read_text(encoding="utf-8"))
if data.get("symbol")!="NVDA" or data.get("api_requests")!=1:
    raise SystemExit("NVDA_READ_ERROR=unexpected_json")
articles=data.get("articles")
if not isinstance(articles,list):
    raise SystemExit("NVDA_READ_ERROR=articles_missing")
print("NVDA_ARTICLE_LINKS_COUNT="+str(len(articles)),flush=True)
for i,a in enumerate(articles,1):
    if not isinstance(a,dict):continue
    url=str(a.get("url") or "")
    parts=urlsplit(url)
    if parts.scheme not in ("http","https") or not parts.netloc:
        url=""
    row={"n":i,"title":str(a.get("headline") or "")[:400],
         "url":url,"source":str(a.get("source") or "")[:120],
         "published_at":str(a.get("created_at") or "")[:64]}
    print("NVDA_ARTICLE_LINK="+json.dumps(row,ensure_ascii=False),flush=True)
print("NVDA_ARTICLE_LINKS_DONE",flush=True)
