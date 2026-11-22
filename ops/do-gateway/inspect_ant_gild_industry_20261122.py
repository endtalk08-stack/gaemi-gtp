"""Read-only check for newly listed ANT and the next biotech market-cap candidate."""
import json
import sys
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers.kiwoom_us_industries import fetch_us_industry_maps, fetch_us_industry_stocks
from backend.providers.kiwoom_us_industry import fetch_us_stock_industry
from backend.providers.kiwoom_us_quotes import fetch_us_quote

def safe_call(fn):
    try:
        return fn()
    except Exception as exc:
        return {"error": type(exc).__name__}

def main():
    maps = fetch_us_industry_maps()["heatmap"]
    groups = {row["key"]: row for row in maps.get("items", [])}
    result = {"groups": {}, "symbols": {}}
    for key in ("software", "biotech"):
        row = groups.get(key) or {}
        codes = row.get("codes") or ([row["code"]] if row.get("code") else [])
        if not codes:
            result["groups"][key] = {"codes": [], "error": "industry_code_missing"}
            continue
        ranking = safe_call(lambda: fetch_us_industry_stocks(codes, "marketcap", limit=12))
        result["groups"][key] = {
            "codes": codes,
            "items": [
                {name: stock.get(name) for name in ("symbol", "name", "market_cap_usd", "change_pct")}
                for stock in ranking.get("items", [])
            ] if isinstance(ranking, dict) and isinstance(ranking.get("items"), list) else ranking,
        }
    for symbol in ("ANT", "GILD"):
        result["symbols"][symbol] = {
            "industry": safe_call(lambda s=symbol: fetch_us_stock_industry(s, "ND")),
            "quote": safe_call(lambda s=symbol: fetch_us_quote(s, "ND")),
        }
    print("ANT_GILD_KIWOOM_PROBE=" + json.dumps(result, allow_nan=False), flush=True)

if __name__ == "__main__":
    main()
