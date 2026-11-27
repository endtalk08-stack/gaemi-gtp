"""Read-only: dump selected deployed news modules (source code only, no secrets) as base64."""
import base64
import pathlib

APP = pathlib.Path("/opt/gaemigtp-news/app/backend")
for name in ("news_worker.py", "services/news_r2_ai.py", "services/r2_news_uploader.py", "tradingview_news_worker.py",
             "providers/naver_news.py"):
    p = APP / name
    if not p.exists():
        print("MISSING " + name, flush=True)
        continue
    enc = base64.b64encode(p.read_bytes()).decode()
    for i in range(0, len(enc), 300):
        print("SRC|%s|%s" % (name, enc[i:i + 300]), flush=True)
