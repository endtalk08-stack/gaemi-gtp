"""Read-only live NVDA stock-news pipeline probe. No AI, DB, R2 or saved-state writes."""
import json
import sys
from collections import Counter
from urllib.parse import urlparse

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.services import news_feed, news_detail

def main():
    print("NVDA_PIPELINE_BEGIN", flush=True)
    rows = news_feed.fetch_stock_news("엔비디아", market="미국", limit=20, raise_on_error=True)
    urls = [str(x.get("url") or x.get("link") or "").strip() for x in rows]
    valid_urls = [u for u in urls if u.startswith(("https://", "http://"))]
    print("NVDA_PIPELINE_COUNTS=" + json.dumps({
        "total": len(rows),
        "unique_urls": len(set(valid_urls)),
        "duplicate_urls": len(valid_urls) - len(set(valid_urls)),
        "providers": dict(Counter(str(x.get("provider") or x.get("source_provider") or "unknown") for x in rows)),
        "source_types": dict(Counter(str(x.get("source_type") or "unknown") for x in rows)),
    }, ensure_ascii=False), flush=True)
    for i, item in enumerate(rows[:12], 1):
        url = str(item.get("url") or item.get("link") or "").strip()
        print("NVDA_ARTICLE=" + json.dumps({
            "rank": i,
            "title": str(item.get("title") or "")[:180],
            "description": str(item.get("description") or "")[:220],
            "published_at": item.get("published_at"),
            "provider": item.get("provider") or item.get("source_provider"),
            "source_type": item.get("source_type"),
            "domain": urlparse(url).netloc if url else "",
            "url": url[:420],
        }, ensure_ascii=False), flush=True)
    for i, item in enumerate(rows[:3], 1):
        url = str(item.get("url") or item.get("link") or "").strip()
        if not url.startswith(("https://", "http://")):
            continue
        try:
            detail = news_detail._read_url(url, with_source=True)
            text = str(detail.get("text") or "")
            print("NVDA_DETAIL=" + json.dumps({
                "rank": i,
                "source": detail.get("source"),
                "body_length": len(text),
                "excerpt": text[:260],
            }, ensure_ascii=False), flush=True)
        except Exception as exc:
            print("NVDA_DETAIL_ERROR=" + json.dumps({
                "rank": i, "error": type(exc).__name__,
            }, ensure_ascii=False), flush=True)
    print("NVDA_PIPELINE_COMPLETE", flush=True)

if __name__ == "__main__":
    main()
