"""One read-only request to a public GlobeNewswire RSS feed; inspect one item.
No article-page fetch, API keys, saves, service changes or database operations.
"""
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
import html
import re
import xml.etree.ElementTree as ET
import json
URL = "https://www.globenewswire.com/RssFeed/subjectcode/13-Earnings%20Releases%20and%20Operating%20Results/feedTitle/GlobeNewswire%20-%20Earnings%20Releases%20and%20Operating%20Results"
def clean(value):
    return re.sub(r"\\s+"," ",html.unescape(re.sub(r"<[^>]+>", " ",value or ""))).strip()
def localname(tag):
    return str(tag).rsplit("}",1)[-1]
def main():
    print("RSS_AUDIT=one_remote_RSS_GET_one_item_only",flush=True)
    request=Request(URL, headers={"User-Agent":"gaemiGTP-readonly-rss-audit/1.0","Accept":"application/rss+xml, application/xml, text/xml"})
    try:
        with urlopen(request, timeout=12) as response:
            data=response.read(1000000)
            print("RSS_HTTP_STATUS",response.status,"BYTES",len(data),flush=True)
    except HTTPError as e:
        print("RSS_HTTP_ERROR",e.code,flush=True); return
    except (OSError,URLError) as e:
        print("RSS_NETWORK_ERROR",type(e).__name__,flush=True);return
    try:
        root=ET.fromstring(data)
    except ET.ParseError:
        print("RSS_PARSE_ERROR",flush=True);return
    first=next((x for x in root.iter() if localname(x.tag) in ("item","entry")),None)
    if first is None:
        print("RSS_EMPTY_ITEMS",flush=True);return
    fields={}
    for child in first:
        key=localname(child.tag)
        val="".join(child.itertext()).strip()
        fields[key]={"chars":len(clean(val)),"sample":clean(val)[:180] if key in ("title","description","summary") else ""}
    print("RSS_FIRST_ITEM",json.dumps(fields,ensure_ascii=False),flush=True)
    for k in ("description","summary","content","encoded","fullText","body"):
        nodes=[v for v in first if localname(v.tag).lower()==k.lower()]
        if nodes:
            value=clean(" ".join("".join(v.itertext()) for v in nodes))
            print("RSS_BODY_FIELD",k,"chars",len(value),"truncated_indicator",value.endswith(("...","…")),flush=True)
    print("RSS_AUDIT_DONE",flush=True)
if __name__=="__main__":main()
