"""Resolve newly ranked KR/US stocks for DO disclosure collection only.

No Render requests and no news-worker modifications. Official DART corp codes
and SEC CIKs are looked up only for ranked symbols missing from the existing
validated mappings; previous verified mappings remain in use on source failure.
"""
import io
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile


def _ranked_symbols():
    from . import market_rankings

    providers = (
        ("KR", market_rankings.build_kr_popular_result),
        ("KR", market_rankings.build_kr_trading_value_result),
        ("US", market_rankings.build_us_popular_result),
        ("US", market_rankings.build_us_trading_value_result),
    )
    ranked = {"KR": set(), "US": set()}
    for market, builder in providers:
        try:
            rows = builder(limit=20)
        except Exception as exc:
            print("DISCLOSURE_RANKING_UNAVAILABLE", market, type(exc).__name__, flush=True)
            continue
        if rows is None:
            print("DISCLOSURE_RANKING_UNAVAILABLE", market, "source_empty", flush=True)
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("analysis_symbol") or row.get("symbol") or "").upper().strip()
            if market == "US" and code.endswith((".N", ".O")):
                code = code[:-2]
            if market == "KR" and re.fullmatch(r"\d{6}", code):
                ranked[market].add(code)
            elif market == "US" and re.fullmatch(r"[A-Z.]{1,10}", code):
                ranked[market].add(code)
    return ranked


def _dart_corp_codes(api_key, needed):
    """Read the official DART exchange crosswalk only for missing ranked codes."""
    if not needed or not api_key:
        return {}
    url = "https://opendart.fss.or.kr/api/corpCode.xml?" + urllib.parse.urlencode(
        {"crtfc_key": api_key}
    )
    request = urllib.request.Request(url, headers={"User-Agent": "gaemiGTP/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        archive = response.read()
    found = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        with package.open("CORPCODE.xml") as source:
            for _, entry in ET.iterparse(source, events=("end",)):
                if entry.tag != "list":
                    continue
                stock = str(entry.findtext("stock_code") or "").strip()
                if stock in needed:
                    corp = str(entry.findtext("corp_code") or "").strip()
                    if re.fullmatch(r"\d{8}", corp):
                        found[stock] = corp
                entry.clear()
                if len(found) == len(needed):
                    break
    return found


def resolve_universe(engine):
    """Extend staged engine mappings from current ranked symbols, without guesses."""
    ranked = _ranked_symbols()
    missing_kr = ranked["KR"] - set(engine.DART_STOCK_CORP_CODES)
    missing_us = ranked["US"] - set(engine.US_CIKS)
    if missing_kr:
        try:
            resolved = _dart_corp_codes(engine.OPENDART_API_KEY, missing_kr)
            engine.DART_STOCK_CORP_CODES.update(resolved)
            print("DISCLOSURE_RANK_KR_RESOLVED", len(resolved), "OF", len(missing_kr), flush=True)
        except Exception as exc:
            print("DISCLOSURE_RANK_KR_RESOLVE_ERROR", type(exc).__name__, flush=True)
    if missing_us:
        try:
            directory = engine.sec_filings._ticker_directory()
            resolved = {
                symbol: str(directory[symbol]).zfill(10)
                for symbol in missing_us if symbol in directory
            }
            engine.US_CIKS.update(resolved)
            print("DISCLOSURE_RANK_US_RESOLVED", len(resolved), "OF", len(missing_us), flush=True)
        except Exception as exc:
            print("DISCLOSURE_RANK_US_RESOLVE_ERROR", type(exc).__name__, flush=True)
    return {
        "KR": sorted(engine.DART_STOCK_CORP_CODES),
        "US": sorted(engine.US_CIKS),
    }
