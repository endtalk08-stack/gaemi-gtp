"""Google News RSS provider.

Responsibility:
- Call Google News RSS.
- Return source-shaped raw records.
- Do NOT classify, rank, deduplicate, format time, or decide UI behavior.
"""

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def fetch_news(query, days=2):
    search_query = f"{str(query or '').strip()} when:{max(1, int(days))}d"
    url = (
        "https://news.google.com/rss/search?"
        + urllib.parse.urlencode({
            "q": search_query,
            "hl": "ko",
            "gl": "KR",
            "ceid": "KR:ko",
        })
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            root = ET.fromstring(resp.read())
    except Exception as exc:
        print(f"[provider:google-news] failed query={query}: {type(exc).__name__}: {exc}")
        return []

    rows = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        source_el = item.find("source")
        pub_el = item.find("pubDate")
        link_el = item.find("link")
        rows.append({
            "provider": "google",
            "raw_title": title_el.text if title_el is not None else "",
            "raw_source": source_el.text if source_el is not None else "",
            "raw_pub_date": pub_el.text if pub_el is not None else "",
            "raw_link": link_el.text if link_el is not None else "",
            "raw_original_link": "",
        })
    return rows
