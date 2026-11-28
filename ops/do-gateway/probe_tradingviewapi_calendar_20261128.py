"""Read-only: tradingviewapi.com docs for the calendar endpoints (parameters and response fields)."""
import html, re, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (compatible; research/1.0)"}
with urllib.request.urlopen(urllib.request.Request("https://www.tradingviewapi.com/docs/", headers=UA), timeout=30) as r:
    page = r.read().decode("utf-8", "replace")
page = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", page)
doc = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))
for ep in ("/api/calendar/economic", "/api/calendar/earnings", "/api/calendar/ipo", "/api/calendar/revenue"):
    i = doc.find("GET " + ep)
    print("\nEP %s at=%d" % (ep, i), flush=True)
    if i >= 0:
        print("  " + doc[i:i + 2600], flush=True)
