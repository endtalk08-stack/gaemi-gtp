"""Read-only, no AI: for the last run, articles/bodies/tokens per stock; and for 5 TOP20 stocks now,
each selected article with its full body length (what 1,200 chars would cut)."""
import json, os, pathlib, re, sys
sys.path.insert(0, "/opt/gaemigtp-news/app")
for line in pathlib.Path("/var/lib/gaemigtp-news/r2.env").read_text().splitlines():
    m = re.match(r"^(?:export\s+)?(R2_[A-Z_]+)\s*=\s*(.*)$", line.strip())
    if m:
        os.environ[m.group(1)] = m.group(2).strip().strip("'\"")
for line in pathlib.Path("/etc/gaemigtp/news-worker.env").read_text().splitlines() if os.access("/etc/gaemigtp/news-worker.env", os.R_OK) else []:
    pass
from backend.services.r2_news_uploader import read_r2_json
import backend.us_news_ai_daily as job
try:
    top = read_r2_json("news/ai/us/TOP20.json")
    print("LAST_RUN day=%s" % (top or {}).get("exchange_day"), flush=True)
    for it in (top or {}).get("items") or []:
        d = it.get("diagnostics") or {}
        print("RUN %-5s %-8s articles=%s bodies=%s tokens=%s" % (it.get("symbol"), it.get("status"), d.get("articles"), d.get("bodies"), it.get("tokens")), flush=True)
except Exception as exc:
    print("LAST_RUN_ERROR", type(exc).__name__, flush=True)
from backend.services.news_feed import fetch_stock_news
from backend.services.news_detail import read_selected_article_details
stocks = job.read_top20()[:5]
for stock in stocks:
    raw = fetch_stock_news(stock["name"], market="미국", limit=50) or []
    arts = job.select_articles(stock, raw)
    print("\nSTOCK %s %s fetched=%d selected=%d" % (stock["symbol"], stock["name"], len(raw), len(arts)), flush=True)
    if not arts:
        continue
    details = read_selected_article_details([{"title": a["title"], "url": a["url"]} for a in arts], limit=len(arts), with_sources=True) or []
    for a, det in zip(arts, details):
        text = str((det or {}).get("text") or "").strip() if isinstance(det, dict) else ""
        used = "본문" if len(text) >= 300 else "요약"
        print("  ART %s | %s | 본문길이=%d | 사용=%s | 잘림=%s | %s" % (
            a["_published"].astimezone(job.KST).strftime("%m-%d %H:%M"), (a.get("source") or "")[:10],
            len(text), used, "예" if len(text) > job.BODY_CHARS else "아니오", a["title"][:60]), flush=True)
