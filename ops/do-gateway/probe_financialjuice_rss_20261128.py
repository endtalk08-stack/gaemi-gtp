"""Read-only: what the FinancialJuice RSS feed delivers (titles, times, tags). Nothing stored."""
import collections, re, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
UA = {"User-Agent": "Mozilla/5.0 (compatible; news-probe/1.0)", "Accept": "application/rss+xml, */*"}
for url in ("https://www.financialjuice.com/feed.ashx?xy=rss", "https://www.financialjuice.com/rss"):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            raw = r.read()
        root = ET.fromstring(raw)
    except Exception as exc:
        print("FEED_FAIL %s %s" % (url, type(exc).__name__), flush=True)
        continue
    items = list(root.iter("item"))
    print("FEED_OK %s items=%d bytes=%d" % (url, len(items), len(raw)), flush=True)
    times, tags = [], collections.Counter()
    for it in items:
        title = re.sub(r"\s+", " ", it.findtext("title") or "").strip()
        try:
            t = parsedate_to_datetime(it.findtext("pubDate") or "")
            times.append(t)
        except Exception:
            t = None
        cats = [c.text for c in it.findall("category") if c.text]
        tags.update(cats)
        desc = re.sub(r"<[^>]+>|\s+", " ", it.findtext("description") or "").strip()
        print("ITEM %s | %s | %s%s" % (t.strftime("%m-%d %H:%M") if t else "-", ",".join(cats)[:40], title[:150],
              (" | DESC " + desc[:80]) if desc and desc != title else ""), flush=True)
    if len(times) > 1:
        span = (max(times) - min(times)).total_seconds() / 3600
        print("SPAN %.1f hours for %d items (%.1f per hour)" % (span, len(times), len(times) / max(span, 0.01)), flush=True)
    print("TAGS " + str(tags.most_common(20)), flush=True)
    break
