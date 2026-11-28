"""Read-only: fetch tradingviewapi.com pricing, docs and terms; print the parts about news and redistribution."""
import html, re, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (compatible; research/1.0)"}
def text(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
            page = r.read().decode("utf-8", "replace")
    except Exception as exc:
        return None, "FAIL %s" % type(exc).__name__
    page = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page))).strip(), page
KEYS = re.compile(r"news|headline|redistribut|resell|resale|commercial|public|display|republish|third[- ]party|affiliat|own(ership)?|licen[cs]e|attribution|cache|store|personal use|prohibit|may not|must not", re.I)
for url in ("https://www.tradingviewapi.com/", "https://www.tradingviewapi.com/pricing/", "https://www.tradingviewapi.com/terms/",
            "https://www.tradingviewapi.com/docs/", "https://www.tradingviewapi.com/privacy/"):
    body, raw = text(url)
    if body is None:
        print("PAGE %s %s" % (url, raw), flush=True); continue
    print("\nPAGE %s chars=%d" % (url, len(body)), flush=True)
    links = sorted(set(re.findall(r'href="(/[a-z0-9/_-]*)"', raw)))[:60]
    print("LINKS " + " ".join(links), flush=True)
    sentences = re.split(r"(?<=[.!?])\s+", body)
    shown = 0
    for s in sentences:
        if KEYS.search(s) and 25 < len(s) < 600:
            print("  S " + s, flush=True); shown += 1
            if shown >= 45: break
