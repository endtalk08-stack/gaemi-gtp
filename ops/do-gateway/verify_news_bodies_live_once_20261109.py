"""Read-only verification: Cloudflare Pages news endpoint and detail renderer."""
import json
import urllib.request
import urllib.error

BASE = "https://gaemigtp-news.pages.dev"
def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "gaemigtp-news-verification/1.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read(5000000)
try:
    hs, html = get("/")
    js, raw = get("/news/latest.json")
    d = json.loads(raw)
    rows = d.get("items", [])
    bodies = sum(bool(x.get("body")) for x in rows)
    print("LIVE_SITE_VERIFY="+json.dumps({
        "html_status": hs, "endpoint_status": js,
        "news_items": len(rows), "body_items": bodies,
        "detail_panel_present": b'detArticleContent' in html,
        "detail_body_renderer_present": b'n.body||' in html,
    }), flush=True)
    if hs != 200 or js != 200 or len(rows) != 24 or bodies != 23 or b'detArticleContent' not in html or b'n.body||' not in html:
        raise SystemExit("LIVE_SITE_VERIFY_FAILED")
    print("LIVE_SITE_VERIFY_PASS=1", flush=True)
except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
    print("LIVE_SITE_VERIFY_ERROR="+type(exc).__name__, flush=True)
    raise
