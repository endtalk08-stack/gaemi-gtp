"""Read-only production probe for the US industry heatmap percentage fields."""
import json
import ssl
import urllib.request

def main():
    request = urllib.request.Request(
        "https://127.0.0.1/market/us-industries?include_stocks=1&view=heatmap",
        headers={
            "Origin": "https://gaemigtp-main.pages.dev",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context())
    )
    with opener.open(request, timeout=35) as response:
        data = json.load(response)
        result = {
            "http_status": response.status,
            "ok": data.get("ok"),
            "view": data.get("view"),
            "source": data.get("source"),
            "fetched_at": data.get("fetched_at"),
            "heatmap_ready": data.get("heatmap_ready"),
            "heatmap_missing": data.get("heatmap_missing"),
            "items": [
                {
                    key: row.get(key)
                    for key in ("key", "name", "change_pct", "mapping_status", "change_method", "codes")
                }
                for row in data.get("items", [])
                if isinstance(row, dict)
            ],
        }
    print("LIVE_US_INDUSTRY_PCT=" + json.dumps(result, allow_nan=False), flush=True)

if __name__ == "__main__":
    main()
