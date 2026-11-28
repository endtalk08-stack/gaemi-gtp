"""Publish AI articles now (user request, weekend): TOP20 stocks 1-10, one AI call per stock, to R2."""
import datetime as dt, json, os, pathlib, re, sys, time
sys.path.insert(0, "/opt/gaemigtp-news/app")
for line in pathlib.Path("/var/lib/gaemigtp-news/r2.env").read_text().splitlines():
    m = re.match(r"^(?:export\s+)?(R2_[A-Z_]+)\s*=\s*(.*)$", line.strip())
    if m:
        os.environ[m.group(1)] = m.group(2).strip().strip("'\"")
import backend.us_news_ai_daily as job
START, END = 0, 10
SAVE = pathlib.Path("/var/lib/gaemigtp-news/ai-publish-now-20261128.json")
DAY = dt.date(2026, 11, 27)               # last US trading day (Friday)
now = dt.datetime.now(dt.timezone.utc)
profiles = job.intro_map(job.read_state(job.STATE_PATH).get("profiles") or {}, job.read_manual_intros())
items = json.loads(SAVE.read_text()) if START and SAVE.exists() else []
stocks = job.read_top20()
for n, stock in enumerate(stocks[START:END]):
    if n:
        time.sleep(30)
    stamp = dt.datetime.now(dt.timezone.utc)
    status, result, articles, tokens = "failed", None, [], None
    try:
        raw = job.__dict__.get("fetch_stock_news") or None
        from backend.services.news_feed import fetch_stock_news
        raw = fetch_stock_news(stock["name"], market="미국", limit=50, raise_on_error=True) or []
        articles = job.attach_bodies(job.select_articles(stock, raw, now=now))
        if not articles:
            status = "no_news"
        else:
            result, tokens = job.call_groq(job.build_user_message(stock, articles, profiles.get(stock["symbol"])))
            if isinstance(result, dict) and result.get("type") == "none":
                status, result = "no_news", None
            else:
                problems = job.validate(result, len(articles), company_terms=job.title_terms(stock))
                status = "ok" if not problems else "invalid"
                if problems:
                    print("PROBLEMS %s %s" % (stock["symbol"], problems), flush=True)
                    result = None
    except Exception as exc:
        print("ERROR %s %s" % (stock["symbol"], type(exc).__name__), flush=True)
    payload = job.stock_payload(stock, DAY, stamp, status=status, result=result, articles=articles, tokens=tokens)
    if status == "ok":
        job.upload_json(payload, "news/ai/us/%s.json" % stock["symbol"])
    items.append(payload)
    SAVE.write_text(json.dumps(items, ensure_ascii=False))
    counts = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    job.upload_json({"ok": True, "market": "US", "exchange_day": DAY.isoformat(), "generated_at": stamp.isoformat(),
                     "complete": END == 20 and n == END - START - 1, "counts": counts, "items": items},
                    "news/ai/us/TOP20.json")
    print("PUB #%s %s %s tokens=%s %s" % (stock["rank"], stock["symbol"], status, tokens,
          (result or {}).get("headline", "")), flush=True)
