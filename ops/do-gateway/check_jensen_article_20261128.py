"""Read-only: find the '젠슨 황 아무 문제 없다' article, print its time and whether the body mentions a return."""
import re
import sys

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.services import news_feed
from backend.services.news_detail import read_selected_article_details

raw = news_feed.fetch_stock_news("엔비디아", market="미국", limit=50, raise_on_error=True) or []
hits = [a for a in raw if isinstance(a, dict) and ("젠슨 황" in str(a.get("title") or "") or "젠슨황" in str(a.get("title") or ""))]
print("TOTAL %d JENSEN_TITLES %d" % (len(raw), len(hits)), flush=True)
for a in hits[:5]:
    print("ART %s | %s | %s" % (a.get("published_at") or a.get("pubDate"), a.get("source"), str(a.get("title"))[:90]), flush=True)
    print("  DESC " + str(a.get("description") or "")[:300], flush=True)
target = [a for a in hits if "아무 문제" in str(a.get("title") or "")]
if target:
    a = target[0]
    detail = read_selected_article_details([{"title": a.get("title"), "url": a.get("url") or a.get("link")}], limit=1, with_sources=True)
    text = str((detail[0] or {}).get("text") or "") if detail else ""
    print("BODY_CHARS %d" % len(text), flush=True)
    for word in ("복귀", "귀환", "사임", "해임", "물러", "퇴진", "CEO"):
        spots = [m.start() for m in re.finditer(word, text)]
        print("WORD %s count=%d" % (word, len(spots)), flush=True)
        for pos in spots[:2]:
            print("  ..." + text[max(0, pos - 80): pos + 80].replace("\n", " ") + "...", flush=True)
    print("BODY_HEAD " + text[:700].replace("\n", " "), flush=True)
else:
    print("TARGET_NOT_FOUND", flush=True)
