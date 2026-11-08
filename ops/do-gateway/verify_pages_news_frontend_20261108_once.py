"""Read-only verification of the current Cloudflare Pages news UI and R2 route."""
from __future__ import annotations
import hashlib
import json
import urllib.request
import urllib.error

BASE = "https://gaemigtp-news.pages.dev"
EXPECTED_HTML_SHA256_PREFIX = "2ec73cf4337650938d89d8dabb0c9695"
def check(path):
    try:
        with urllib.request.urlopen(urllib.request.Request(
            BASE+path,headers={"User-Agent":"gaemi-news-deploy-verify/1.0",
                               "Cache-Control":"no-cache"}),timeout=18) as r:
            return r.status,r.headers.get("Content-Type",""),r.read()
    except urllib.error.HTTPError as exc:
        return exc.code,exc.headers.get("Content-Type",""),exc.read(800)

status,ctype,body=check("/")
hash=hashlib.sha256(body).hexdigest()[:32]
html=body.decode("utf-8","replace")
print("PAGES_HOME_STATUS="+str(status),flush=True)
print("PAGES_HOME_CONTENT_TYPE="+ctype,flush=True)
print("PAGES_HTML_SHA256_PREFIX="+hash,flush=True)
print("PAGES_EXPECTED_HTML_MATCH="+str(hash==EXPECTED_HTML_SHA256_PREFIX),flush=True)
print("PAGES_NEWS_LIST_SUMMARY_HIDDEN="+str("n.summary?'<p" not in html),flush=True)
print("PAGES_MARKET_CATEGORIES="+str("marketMenuCodes" in html),flush=True)

nstatus,nctype,nbody=check("/news/latest.json")
print("NEWS_LATEST_STATUS="+str(nstatus),flush=True)
print("NEWS_LATEST_CONTENT_TYPE="+nctype,flush=True)
if nstatus==200:
    try:
        j=json.loads(nbody)
        print("NEWS_LATEST_JSON_OK="+str(isinstance(j,dict) and isinstance(j.get("items"),list)),flush=True)
        print("NEWS_LATEST_ITEMS="+str(len(j.get("items",[]))),flush=True)
    except ValueError:
        print("NEWS_LATEST_JSON_OK=False",flush=True)
else:
    print("NEWS_LATEST_RESPONSE_CODE="+str(nstatus),flush=True)
assert status==200 and hash==EXPECTED_HTML_SHA256_PREFIX,"new_pages_html_not_live"
assert nstatus==200,"news_latest_route_not_200"
print("PAGES_NEWS_DEPLOY_VERIFY_PASS=1",flush=True)
