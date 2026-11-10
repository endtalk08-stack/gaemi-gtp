"""Read existing public Pages homepage for a faithful, minimal modification.
No secrets or session data are read. Outputs public HTML encoded as base64.
"""
import urllib.request,base64,hashlib
req=urllib.request.Request("https://gaemigtp-news.pages.dev/",headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
with urllib.request.urlopen(req,timeout=15) as resp:
    raw=resp.read(150000)
    print("LIVE_HTML_STATUS",resp.status)
    print("LIVE_HTML_CONTENT_TYPE",resp.headers.get("Content-Type"))
    print("LIVE_HTML_SHA256",hashlib.sha256(raw).hexdigest())
    print("LIVE_HTML_B64_START")
    print(base64.b64encode(raw).decode("ascii"))
    print("LIVE_HTML_B64_END")
