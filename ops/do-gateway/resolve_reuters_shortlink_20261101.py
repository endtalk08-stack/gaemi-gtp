"""Resolve the Reuters short source link only; never request TradingView storyPath."""
import urllib.request,re,subprocess
assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True).stdout.strip()=="inactive"
url="https://tinyurl.com/48732ndf"
req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; gaemiGTP-source-link-check/1.0)","Accept":"text/html"})
try:
    with urllib.request.urlopen(req,timeout=15) as r:
        body=r.read(250000).decode("utf-8","replace")
        print("SHORTLINK_STATUS",r.status,flush=True)
        print("SHORTLINK_FINAL_URL",r.geturl(),flush=True)
        print("SHORTLINK_CONTENT_TYPE",r.headers.get("Content-Type",""),flush=True)
        m=re.search(r"<title[^>]*>(.*?)</title>",body,re.I|re.S)
        print("SHORTLINK_HTML_TITLE",re.sub(r"\s+"," ",m.group(1)).strip()[:300] if m else "NOT_FOUND",flush=True)
        print("SHORTLINK_BODY_BYTES",len(body),flush=True)
except Exception as exc:
    print("SHORTLINK_ERROR",type(exc).__name__,str(exc)[:300],flush=True)
assert subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True).stdout.strip()=="inactive"
print("SHORTLINK_CHECK_DONE_WORKER_INACTIVE",flush=True)
