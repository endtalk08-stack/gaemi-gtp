"""Dry run (nothing published): current AI article job on TOP20 stocks 1-10, weekend check skipped."""
import datetime as dt, json, re, sys, time
sys.path.insert(0, "/opt/gaemigtp-news/app")
import backend.us_news_ai_daily as job
START, END = 0, 10
now = dt.datetime.now(dt.timezone.utc)
print("WINDOW since %s" % job.previous_close(now).astimezone(job.KST).strftime("%m-%d %H:%M KST"), flush=True)
profiles = job.intro_map(job.read_state(job.STATE_PATH).get("profiles") or {}, job.read_manual_intros())
stocks = job.read_top20()[START:END]
total = 0
for n, stock in enumerate(stocks):
    if n:
        time.sleep(35)          # stay under the Groq free tier (8,000 tokens a minute)
    try:
        status, result, articles, tokens, diag = job.analyze_stock(stock, profiles, now=now)
    except Exception as exc:
        print("\nSTOCK #%s %s %s ERROR %s" % (stock["rank"], stock["symbol"], stock["name"], type(exc).__name__), flush=True)
        continue
    total += tokens or 0
    pct = stock.get("change_pct")
    print("\nSTOCK #%s %s %s (%s%%) status=%s tokens=%s diag=%s" % (stock["rank"], stock["symbol"], stock["name"],
          "%+.2f" % pct if isinstance(pct, (int, float)) else "-", status, tokens, json.dumps(diag, ensure_ascii=False)), flush=True)
    for i, a in enumerate(articles, 1):
        print("  SRC[%d] %s %s%s" % (i, a["_published"].astimezone(job.KST).strftime("%m-%d %H:%M"),
              "본문 " if a.get("body") else "요약 ", a["title"][:70]), flush=True)
    if result:
        lines = result.get("lines") or []
        body = " ".join(lines[:2])
        print("  TYPE %s | 근거 %s" % (result.get("type"), result.get("source_ids")), flush=True)
        print("  TITLE " + str(result.get("headline")), flush=True)
        for l in lines:
            print("  LINE " + l, flush=True)
        kws = result.get("keywords") or []
        miss = [k for k in kws if not any(w in body for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", k))]
        print("  KEYWORDS %s | 대표=%s | 본문에 없는 키워드=%s" % (kws, result.get("headline_keyword"), miss or "없음"), flush=True)
print("\nTOKENS_TOTAL %d" % total, flush=True)
