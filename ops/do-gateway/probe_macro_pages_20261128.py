"""Read-only: see how official release pages start, to pick the summary paragraph."""
import json, pathlib, re, urllib.request
import xml.etree.ElementTree as ET
UA = {"User-Agent": "Mozilla/5.0 (compatible; gaemiGTP-news/1.0)"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read().decode("utf-8", "replace")
urls = [row["url"] for row in json.loads(pathlib.Path("/var/lib/gaemigtp-news/us-macro-news-state.json").read_text())["items"]]
for feed in ("https://www.federalreserve.gov/feeds/press_monetary.xml", "https://www.federalreserve.gov/feeds/press_all.xml",
             "https://www.whitehouse.gov/presidential-actions/feed/"):
    root = ET.fromstring(get(feed).encode())
    item = next(root.iter("item"))
    urls.append(item.findtext("link").strip())
    print("FEED_DESC %s | %s" % (feed, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", item.findtext("description") or ""))[:300]), flush=True)
for url in urls:
    try:
        html = get(url)
    except Exception as exc:
        print("PAGE_FAIL %s %s" % (url, type(exc).__name__)); continue
    html = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html)
    paras = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p)).strip() for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", html)]
    paras = [p for p in paras if len(p) > 60]
    print("\nPAGE %s" % url, flush=True)
    for p in paras[:4]:
        print("  P: " + p[:400], flush=True)
