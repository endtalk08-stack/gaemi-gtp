"""The only searchable/news/disclosure stock identities for the 40-company edition.

Pure data: no price API, no collection, no AI, no timers. Market rankings are
separate and never sorted/filtered through this catalog.
"""
import re

from .disclosure_universe import KR_COMPANIES, US_COMPANIES

_US_ALIASES = {
    "NVDA": ("NVIDIA", "엔비디아"),
    "AAPL": ("Apple", "애플"),
    "GOOGL": ("GOOG", "구글", "Google", "Alphabet", "알파벳 Class A", "알파벳 Class C"),
    "MSFT": ("Microsoft", "마이크로소프트"),
    "AMZN": ("Amazon", "아마존닷컴"),
    "TSM": ("TSMC", "TSMC ADR", "Taiwan Semiconductor Manufacturing"),
    "SPCX": ("SpaceX", "스페이스엑스"),
    "META": ("Meta Platforms", "메타"),
    "AVGO": ("Broadcom", "브로드컴"),
    "TSLA": ("Tesla", "테슬라"),
    "BRK.B": ("BRK.A", "Berkshire Hathaway", "버크셔"),
    "LLY": ("Eli Lilly", "일라이 릴리"),
    "SKHY": ("SK하이닉스 ADR", "SK hynix ADR", "SKHY"),
    "MU": ("마이크론 테크놀로지", "마이크론", "Micron Technology"),
    "WMT": ("Walmart", "월마트"),
    "JPM": ("JPMorgan", "JP모건", "제이피모건"),
    "AMD": ("Advanced Micro Devices", "에이엠디"),
    "V": ("Visa", "비자"),
    "XOM": ("Exxon Mobil", "엑슨모빌"),
    "ASML": ("ASML Holding", "에이에스엠엘"),
}
_KR_ALIASES = {
    "005380": ("현대자동차",),
    "000660": ("하이닉스",),
    "055550": ("신한금융",),
    "032830": ("삼성생명보험",),
}

def _rows():
    for market, companies, extras in (("KR", KR_COMPANIES, _KR_ALIASES),
                                       ("US", US_COMPANIES, _US_ALIASES)):
        for ticker, (name, filing_id) in companies.items():
            aliases = tuple(dict.fromkeys((name, ticker, *extras.get(ticker, ()))))
            yield {
                "market": market,
                "symbol": ticker,
                "name": name,
                "aliases": aliases,
                "company_key": market + ":" + ticker,
            }

STOCKS = tuple(_rows())
BY_CODE = {(r["market"], r["symbol"]): r for r in STOCKS}
assert len(STOCKS) == len(BY_CODE) == 40

def _code(symbol):
    text = str(symbol or "").strip().upper()
    if text.endswith((".O", ".N", ".K")):
        text = text[:-2]
    return {"GOOG": "GOOGL", "BRK.A": "BRK.B"}.get(text, text)

def resolve_stock(value=None, *, market=None, symbol=None):
    """Exact code or known alias; reject ambiguous values and name/code mismatch."""
    market = str(market or "").strip().upper()
    if market in ("국내", "KR"): market = "KR"
    elif market in ("미국", "US"): market = "US"
    elif market: return None
    code = _code(symbol)
    # When a market+code is supplied, validate any accompanying display label.
    if code:
        matches = [BY_CODE[(m, code)] for m in ((market,) if market else ("KR", "US"))
                   if (m, code) in BY_CODE]
        if len(matches) != 1: return None
        selected = matches[0]
        if value and str(value).strip().casefold() not in {s.casefold() for s in selected["aliases"]}:
            return None
        return selected
    val = str(value or "").strip()
    if not val or len(val) > 90: return None
    key = _code(val)
    matches = [r for r in STOCKS if (not market or market == r["market"])
               and (key == r["symbol"] or val.casefold() in {s.casefold() for s in r["aliases"]})]
    return matches[0] if len(matches) == 1 else None

def public_stock_rows():
    """Only names and identity, not live quotes, ranks, market cap or price data."""
    return [{"market": r["market"], "symbol": r["symbol"], "name": r["name"]}
            for r in STOCKS]
