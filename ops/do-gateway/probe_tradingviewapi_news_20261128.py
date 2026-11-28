"""Read-only: tradingviewapi.com news docs, news use-case page and plan table."""
import html, re, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (compatible; research/1.0)"}
def text(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
        page = r.read().decode("utf-8", "replace")
    page = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page))).strip()
docs = text("https://www.tradingviewapi.com/docs/")
for m in re.finditer(r"/api/news[^\s\"'<]*", docs):
    pass
idx = [m.start() for m in re.finditer(r"(?i)news", docs)]
print("DOCS_NEWS_MENTIONS %d" % len(idx), flush=True)
seen = 0; last = -2000
for i in idx:
    if i - last < 900: continue
    last = i
    print("  D " + docs[max(0, i - 150): i + 750], flush=True)
    seen += 1
    if seen >= 12: break
for url in ("https://www.tradingviewapi.com/use-cases/news/", "https://www.tradingviewapi.com/pricing/"):
    body = text(url)
    print("\nPAGE " + url, flush=True)
    for chunk in re.findall(r".{0,40}(?:\$\d+|requests?/month|req/sec|Basic|Pro|Ultra|Mega|news|provider|language|body|content|real-time|delay).{0,160}", body, re.I)[:40]:
        print("  P " + chunk, flush=True)
