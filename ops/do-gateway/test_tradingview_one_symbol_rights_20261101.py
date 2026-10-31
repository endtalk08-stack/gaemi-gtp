"""One-symbol TradingView Data API rights sample. No cache, DB, AI or worker changes."""
import json, os, subprocess, urllib.parse, urllib.request, urllib.error

SYMBOL = "NASDAQ:NVDA"
BASE = "https://api.tradingviewapi.com"
KEY = os.environ.get("TRADINGVIEW_API_KEY", "").strip()

def worker_state():
    p = subprocess.run(["systemctl", "is-active", "gaemigtp-news.service"],
                       capture_output=True, text=True, timeout=10)
    return p.stdout.strip()

def request_json(url):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + KEY,
        "Accept": "application/json",
        "User-Agent": "gaemiGTP-one-symbol-rights-check/1.0",
    }, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=18) as res:
            raw = res.read(2_000_000)
            return res.status, json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read(1200).decode("utf-8", "replace")
        print("TV_HTTP_ERROR", e.code, body[:800], flush=True)
        raise
    except Exception as e:
        print("TV_REQUEST_ERROR", type(e).__name__, str(e)[:250], flush=True)
        raise

assert KEY, "TRADINGVIEW_API_KEY_NOT_AVAILABLE"
assert worker_state() == "inactive", "NEWS_WORKER_MUST_REMAIN_INACTIVE"
print("TV_TEST_SYMBOL", SYMBOL, flush=True)

# Single symbol-scoped stock-news list request.
params = urllib.parse.urlencode({
    "symbol": SYMBOL,
    "lang": "ko",
    "market_country": "US",
})
list_url = BASE + "/api/news/stock?" + params
status, payload = request_json(list_url)
print("TV_LIST_HTTP_STATUS", status, flush=True)
print("TV_LIST_SUCCESS", payload.get("success") if isinstance(payload, dict) else None, flush=True)
data = payload.get("data") if isinstance(payload, dict) else None
items = data.get("items") if isinstance(data, dict) else (data if isinstance(data, list) else None)
if not isinstance(items, list):
    print("TV_LIST_SHAPE", type(data).__name__, sorted(data.keys())[:80] if isinstance(data, dict) else repr(data)[:500], flush=True)
    raise SystemExit(4)

def symbols_of(item):
    out=set()
    related=item.get("relatedSymbols") or item.get("related_symbols") or []
    if isinstance(related, list):
        for x in related:
            if isinstance(x, dict):
                s=str(x.get("symbol") or "").upper()
            else:
                s=str(x).upper()
            if s:
                out.add(s)
    return out

matches=[x for x in items if isinstance(x,dict) and SYMBOL in symbols_of(x)]
print("TV_LIST_RETURNED_ITEMS", len(items), flush=True)
print("TV_NVDA_MATCHES", len(matches), flush=True)
print("TV_NON_NVDA_ITEMS", len(items)-len(matches), flush=True)

for i, a in enumerate(matches[:12], 1):
    provider=a.get("provider")
    provider_name=provider.get("name") if isinstance(provider,dict) else provider
    print("TV_NEWS", json.dumps({
        "n":i, "id":a.get("id") or a.get("newsId"),
        "title":a.get("title"), "provider":provider_name,
        "permission":a.get("permission"), "paywall":a.get("paywall"),
        "copyright":a.get("copyright"),
        "published":a.get("published"),
        "relatedSymbols":sorted(symbols_of(a)),
        "has_storyPath":bool(a.get("storyPath")),
    },ensure_ascii=False,separators=(",",":"))[:1800], flush=True)

# Inspect up to two detail records, preferring distinct permission classes.
selected=[]
for wanted in ("headline","provider"):
    found=next((a for a in matches if str(a.get("permission") or "").lower()==wanted
                and (a.get("id") or a.get("newsId"))), None)
    if found and found not in selected:
        selected.append(found)
for a in matches:
    if len(selected)>=2: break
    if (a.get("id") or a.get("newsId")) and a not in selected:
        selected.append(a)

for i, article in enumerate(selected,1):
    nid=str(article.get("id") or article.get("newsId"))
    detail_url=BASE+"/api/news/"+urllib.parse.quote(nid,safe="")+"?lang=ko"
    dstatus, detail_payload=request_json(detail_url)
    detail=detail_payload.get("data") if isinstance(detail_payload,dict) else None
    if not isinstance(detail,dict):
        print("TV_DETAIL_SHAPE",i,type(detail).__name__,repr(detail)[:500],flush=True)
        continue
    provider=detail.get("provider")
    provider_name=provider.get("name") if isinstance(provider,dict) else provider
    body=detail.get("astDescription")
    if body is None: body=detail.get("ast_description")
    short=detail.get("shortDescription") or detail.get("short_description")
    summary=detail.get("summary")
    print("TV_DETAIL",json.dumps({
        "n":i,"id":nid,"http_status":dstatus,
        "title":detail.get("title") or article.get("title"),
        "provider":provider_name,
        "list_permission":article.get("permission"),
        "detail_permission":detail.get("permission"),
        "paywall":detail.get("paywall",article.get("paywall")),
        "copyright":detail.get("copyright",article.get("copyright")),
        "astDescription_type":type(body).__name__ if body is not None else None,
        "astDescription_chars":len(body) if isinstance(body,str) else (len(json.dumps(body,ensure_ascii=False)) if body is not None else 0),
        "shortDescription_chars":len(short) if isinstance(short,str) else 0,
        "summary_chars":len(summary) if isinstance(summary,str) else 0,
        "detail_keys":sorted(detail.keys()),
    },ensure_ascii=False,separators=(",",":"))[:4000],flush=True)

assert worker_state() == "inactive", "NEWS_WORKER_STATE_CHANGED"
print("TV_ONE_SYMBOL_RIGHTS_TEST_COMPLETE_WORKER_STILL_INACTIVE", flush=True)
