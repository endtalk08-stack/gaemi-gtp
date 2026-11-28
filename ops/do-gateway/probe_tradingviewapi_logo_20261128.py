"""Read-only: tradingviewapi.com docs for logo images (path, caching, where logos come from)."""
import html, re, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (compatible; research/1.0)"}
def doc(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        page = r.read().decode("utf-8", "replace")
    page = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))
d = doc("https://www.tradingviewapi.com/docs/")
for m in list(re.finditer(r"(?i)logo", d)):
    pass
for key in ("Logo Images", "GET /api/logo", "/api/logo"):
    i = d.find(key)
    print("KEY %s at=%d" % (key, i), flush=True)
    if i >= 0:
        print("  " + d[i:i + 1800], flush=True)
        break
u = doc("https://www.tradingviewapi.com/use-cases/news/")
i = u.find("tv-lo")
print("USECASE " + (u[max(0, i - 200):i + 500] if i >= 0 else "no tv-lo"), flush=True)
