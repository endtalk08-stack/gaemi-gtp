"""Read-only HTTP checks for gaemigtp-main Pages and existing TOP20 origin."""
import json
import urllib.error
import urllib.request

ORIGIN = "https://gaemigtp-main.pages.dev"
CHECKS = [
    ("main", ORIGIN + "/", None),
    ("chart_nvda", ORIGIN + "/market/us-daily-chart?symbol=NVDA", None),
    ("chart_aapl", ORIGIN + "/market/us-daily-chart?symbol=AAPL", None),
    ("top20", "https://quotes.gaemigtp.com/market/trading-value?market=us", ORIGIN),
    ("chart_js", ORIGIN + "/shell/center-chat/widget-dock/widget-dock.js", None),
]
for name, url, origin in CHECKS:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/html, */*"}
    if origin:
        headers["Origin"] = origin
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            body = response.read(200000)
            result = {"label": name, "http": response.status,
                      "type": response.headers.get("Content-Type"),
                      "cors": response.headers.get("Access-Control-Allow-Origin"),
                      "bytes": len(body)}
            if name == "main":
                result["is_html"] = b"<!DOCTYPE html>" in body
                result["title"] = b"gaemiGTP" in body
            elif name == "chart_js":
                result["pages_chart_route"] = b"chartOrigin + '/market/us-daily-chart" in body
            else:
                try:
                    data = json.loads(body)
                    result["ok"] = data.get("ok")
                    result["source"] = data.get("source")
                    result["symbol"] = data.get("symbol")
                    result["count"] = len(data.get("rows") or data.get("items") or [])
                    result["error"] = data.get("error")
                except (ValueError, TypeError):
                    result["json_error"] = body[:120].decode("utf-8", "replace")
            print("MAIN_PAGES_PROBE", json.dumps(result, ensure_ascii=False), flush=True)
    except urllib.error.HTTPError as exc:
        print("MAIN_PAGES_PROBE", name, "HTTP_ERROR", exc.code,
              repr(exc.read(150).decode("utf-8", "replace")), flush=True)
    except Exception as exc:
        print("MAIN_PAGES_PROBE", name, type(exc).__name__, str(exc)[:180], flush=True)
