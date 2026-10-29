"""Find disclosure candidates without restoring deleted popularity/ranking feeds.

DigitalOcean collects DART/SEC. The existing tracked stock names provide KR
candidates; the already-stored Kiwoom US trading-value Top 20 provides changing
US candidates. Only official DART corp codes / SEC CIKs can register a new stock.
On provider failure, retain the previously validated stock mappings.
"""
import io
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile


def _candidate_symbols(engine):
    """Read tracked tickers and the existing Neon Top 20; never fetch rankings."""
    candidates = {"KR": set(), "US": set()}
    tracked = getattr(engine, "TICKERS", {}) or {}
    for raw in tracked.values():
        ticker = str(raw or "").upper().strip()
        if re.fullmatch(r"[0-9]{6}\.(?:KS|KQ)", ticker):
            candidates["KR"].add(ticker[:6])
        elif re.fullmatch(r"[A-Z.]{1,10}", ticker):
            candidates["US"].add(ticker)

    try:
        from .kiwoom_us_value_board import read_us_trading_value_board
        rows = read_us_trading_value_board(limit=20)
        if rows is None:
            print("DISCLOSURE_US_TOP20_UNAVAILABLE", flush=True)
        else:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                ticker = str(row.get("analysis_symbol") or row.get("symbol") or "").upper().strip()
                if re.fullmatch(r"[A-Z.]{1,10}", ticker):
                    candidates["US"].add(ticker)
    except Exception as exc:
        print("DISCLOSURE_US_TOP20_ERROR", type(exc).__name__, flush=True)
    return candidates


def _dart_corp_codes(api_key, needed):
    """Resolve only missing tracked KR symbols using the official OpenDART map."""
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
                    if re.fullmatch(r"[0-9]{8}", corp):
                        found[stock] = corp
                entry.clear()
                if len(found) == len(needed):
                    break
    return found


def resolve_universe(engine):
    """Extend existing verified mappings; do not depend on deleted menus."""
    korean = engine.DART_STOCK_CORP_CODES
    american = engine.US_CIKS
    candidates = _candidate_symbols(engine)
    missing_kr = candidates["KR"] - set(korean)
    missing_us = candidates["US"] - set(american)

    if missing_kr:
        try:
            resolved = _dart_corp_codes(getattr(engine, "OPENDART_API_KEY", ""), missing_kr)
            korean.update({
                symbol: corp for symbol, corp in resolved.items()
                if symbol in missing_kr and re.fullmatch(r"[0-9]{6}", str(symbol))
                and re.fullmatch(r"[0-9]{8}", str(corp))
            })
            print("DISCLOSURE_KR_RESOLVED", len(resolved), "OF", len(missing_kr), flush=True)
        except Exception as exc:
            print("DISCLOSURE_KR_RESOLVE_ERROR", type(exc).__name__, flush=True)

    if missing_us:
        try:
            directory = engine.sec_filings._ticker_directory()
            resolved = {}
            for symbol in missing_us:
                raw = directory.get(symbol)
                try:
                    cik = int(raw)
                except (TypeError, ValueError):
                    continue
                if 0 < cik < 10**10:
                    resolved[symbol] = str(cik).zfill(10)
            american.update(resolved)
            print("DISCLOSURE_US_RESOLVED", len(resolved), "OF", len(missing_us), flush=True)
        except Exception as exc:
            print("DISCLOSURE_US_RESOLVE_ERROR", type(exc).__name__, flush=True)

    return {
        "KR": sorted(
            symbol for symbol, corp in korean.items()
            if re.fullmatch(r"[0-9]{6}", str(symbol))
            and re.fullmatch(r"[0-9]{8}", str(corp))
        ),
        "US": sorted(
            symbol for symbol, cik in american.items()
            if re.fullmatch(r"[A-Z.]{1,10}", str(symbol))
            and re.fullmatch(r"[0-9]{10}", str(cik))
        ),
    }
