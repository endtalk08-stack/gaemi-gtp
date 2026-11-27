"""Dry run (nothing published): pick key sentences from Fed speeches by fixed keywords, translate."""
import html, json, os, pathlib, re, urllib.request
import xml.etree.ElementTree as ET
for line in pathlib.Path("/var/lib/gaemigtp-news/translate.env").read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1); os.environ[k.strip()] = v.strip()
UA = {"User-Agent": "Mozilla/5.0 (compatible; gaemiGTP-news/1.0)"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read().decode("utf-8", "replace")
STRONG = re.compile(r"\b(inflation|policy rate|interest rates?|rate cuts?|rate hikes?|federal funds|monetary policy|"
                    r"labor market|unemployment|employment|economic outlook|outlook|tariffs?|neutral rate|"
                    r"balance sheet|price stability|downside risks?|upside risks?|recession|growth)\b", re.I)
WEAK = re.compile(r"\b(I (?:expect|see|believe|think|support|would|will)|my view|in my view|going forward|"
                  r"supervision|regulation|capital|liquidity|stablecoins?|banks?)\b", re.I)
SKIP = re.compile(r"\.gov website|Secure \.gov|Arrows\]|seeks the video|^Thank you|^Good (morning|afternoon|evening)|"
                  r"pleasure to|honored to|delighted to|footnote|views expressed|do not necessarily", re.I)
def key_lines(page, limit=3):
    page = re.sub(r"(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", page)
    sentences = []
    for raw in re.findall(r"(?is)<p[^>]*>(.*?)</p>", page):
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()
        if len(text) < 60 or SKIP.search(text):
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
            if 50 <= len(s) <= 320 and not SKIP.search(s):
                score = 3 * len(STRONG.findall(s)) + len(WEAK.findall(s))
                sentences.append((score, len(sentences), s))
    best = sorted([x for x in sentences if x[0] >= 3], key=lambda x: (-x[0], x[1]))[:limit]
    return [s for _, _, s in sorted(best, key=lambda x: x[1])], len(sentences)
def deepl(texts):
    key = os.environ["DEEPL_API_KEY"]
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    import urllib.parse
    body = urllib.parse.urlencode([("text", t) for t in texts] + [("source_lang", "EN"), ("target_lang", "KO")]).encode()
    req = urllib.request.Request("https://%s/v2/translate" % host, data=body, method="POST",
                                 headers={"Authorization": "DeepL-Auth-Key " + key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return [t["text"] for t in json.load(r)["translations"]]
root = ET.fromstring(get("https://www.federalreserve.gov/feeds/speeches.xml").encode())
chars = 0
for item in list(root.iter("item"))[:3]:
    title, link = item.findtext("title").strip(), item.findtext("link").strip()
    lines, total = key_lines(get(link))
    print("\nSPEECH %s | %s | sentences=%d" % (item.findtext("pubDate")[:16], title, total), flush=True)
    if not lines:
        print("  (no key sentence)", flush=True); continue
    chars += sum(map(len, lines))
    for en, ko in zip(lines, deepl(lines)):
        print("  EN " + en, flush=True)
        print("  KO " + ko, flush=True)
print("\nCHARS %d" % chars, flush=True)
