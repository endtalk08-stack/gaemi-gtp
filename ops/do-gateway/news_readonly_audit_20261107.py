"""Read-only news deployment audit. Never calls APIs or alters services."""
import hashlib
import json
import pathlib
import subprocess
BASE=pathlib.Path("/opt/gaemigtp-news/app")
for relative in ("backend/providers/tradingview_news_detail.py","backend/providers/tradingview_news_bundle.py","backend/services/tradingview_news_page.py"):
    p=BASE/relative
    print("NEWS_AUDIT_FILE",relative,hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING",flush=True)
for name in ("gaemigtp-news.service","gaemigtp-tradingview-news.service"):
    try:
        proc=subprocess.run(["systemctl","is-active",name],capture_output=True,text=True,timeout=5)
        print("NEWS_AUDIT_SERVICE",name,proc.stdout.strip(),flush=True)
    except Exception as e:
        print("NEWS_AUDIT_SERVICE",name,type(e).__name__,flush=True)
p=pathlib.Path("/var/lib/gaemigtp-news/tradingview-news-bundle.json")
if p.is_file():
    d=json.loads(p.read_text(encoding="utf-8"))
    items=d.get("items",[])
    print("NEWS_AUDIT_CACHE",json.dumps({
        "total":len(items),"checked":sum(bool(x.get("detail_checked")) for x in items),
        "body":sum(bool(x.get("detail_body")) for x in items),
        "description":sum(bool(x.get("detail_description")) for x in items),
        "summary":sum(bool(x.get("detail_summary")) for x in items),
        "shortDescription":sum(bool(x.get("shortDescription")) for x in items),
        "headline":sum(x.get("permission")=="headline" for x in items),
        "sample_keys":sorted({k for x in items[:10] for k in x.keys() if k not in ("title","url","body","description")}),
    },ensure_ascii=False),flush=True)
else: print("NEWS_AUDIT_CACHE MISSING",flush=True)
