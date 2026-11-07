"""One-shot read-only inspection of the DigitalOcean news Pages source and live asset."""
from pathlib import Path
import hashlib
import os
import re
import shutil
import urllib.request

root = Path("/opt/gaemigtp-news/app")
print("CHECK=NEWS_PAGE_SOURCE_READONLY")
print("SERVER_CWD=" + os.getcwd())
for rel in ("frontend/news/index.html", "frontend/index.html", "functions/news/latest.json.js"):
    p = root / rel
    if not p.is_file():
        print("FILE=" + rel + " absent")
        continue
    data = p.read_bytes()
    s = data.decode("utf-8", "replace")
    title = re.search(r"\\.news-title\\s*\\{[^}]*\\}", s)
    summary = re.search(r"\\.news-summary\\s*\\{[^}]*\\}", s)
    print("FILE=" + rel + " bytes=" + str(len(data)) + " sha256=" + hashlib.sha256(data).hexdigest()[:20])
    if title:
        print("TITLE_CSS=" + title.group(0)[:240])
    if summary:
        print("SUMMARY_CSS=" + summary.group(0)[:240])
print("CLI_WRANGLER=" + str(bool(shutil.which("wrangler"))))
print("CLI_CF=" + str(bool(shutil.which("cf"))))
for key in ("CLOUDFLARE_API_TOKEN", "CF_API_TOKEN", "CLOUDFLARE_PAGES_API_TOKEN", "CLOUDFLARE_AUTH_TOKEN"):
    print("CREDENTIAL_PRESENT_" + key + "=" + str(bool(os.getenv(key))))
for base in (root / "ops", root / "backend", root / "frontend"):
    if not base.exists():
        continue
    found = []
    for p in base.glob("*"):
        if p.is_file() and any(z in p.name.lower() for z in ("cloudflare", "wrangler", "pages", "publish")):
            found.append(p.name)
    print("DEPLOY_CANDIDATES=" + str(base) + ":" + ",".join(found[:25]))
for url in ("https://gaemigtp-news.pages.dev/","https://gaemigtp-news.pages.dev/index.html","https://gaemigtp-news.pages.dev/news/"):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"gaemi-readonly-check"}),timeout=9) as r:
            s=r.read(100000).decode("utf-8","replace")
            title=re.search(r"\\.news-title\\s*\\{[^}]*\\}",s)
            summary=re.search(r"\\.news-summary\\s*\\{[^}]*\\}",s)
            print("LIVE_URL="+url+" http="+str(r.status)+" size_prefix="+str(len(s)))
            print("LIVE_TITLE_CSS="+(title.group(0)[:210] if title else "missing"))
            print("LIVE_SUMMARY_CSS="+(summary.group(0)[:210] if summary else "missing"))
    except Exception as e:
        print("LIVE_URL="+url+" CHECK_ERROR="+type(e).__name__+":"+str(e)[:130])
print("CHECK_DONE")
