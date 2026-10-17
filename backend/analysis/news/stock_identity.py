"""Safe stock ticker -> company identity. No external requests, no guesses.

Only confirmed ticker/name combinations may share another stock's news.
Unknown listing names remain independent and are flagged for review in Neon.
"""
import re

# Canonical company news identity, source display names observed in Naver lists.
# Do not infer mergers, ticker transfers, or same-company ownership by fuzzy text.
_VERIFIED = {
    "GOOGL": ("US:ALPHABET", "알파벳", ("알파벳 Class A", "알파벳", "Alphabet Class A", "Alphabet Inc Class A", "Google")),
    "GOOG": ("US:ALPHABET", "알파벳", ("알파벳 Class C", "알파벳", "Alphabet Class C", "Alphabet Inc Class C", "Google")),
    "TSM": ("US:TSM", "TSMC", ("TSMC ADR", "TSMC", "Taiwan Semiconductor Manufacturing")),
    "AMZN": ("US:AMZN", "아마존", ("아마존닷컴", "아마존", "Amazon", "Amazon.com")),
    "PLTR": ("US:PLTR", "팔란티어", ("팔란티어 테크놀로지스", "팔란티어", "Palantir Technologies", "Palantir")),
    "MRVL": ("US:MRVL", "마벨 테크놀로지 그룹", ("마벨 테크놀로지 그룹", "마벨", "Marvell Technology", "Marvell")),
    "AMD": ("US:AMD", "AMD", ("AMD(어드밴스드 마이크로 디바이시스)", "AMD", "Advanced Micro Devices")),
    "NBIS": ("US:NBIS", "네비우스 그룹", ("네비우스 그룹", "네비우스", "Nebius Group")),
    "NVDA": ("US:NVDA", "엔비디아", ("엔비디아", "NVIDIA")),
    "AAPL": ("US:AAPL", "애플", ("애플", "Apple")),
    "MSFT": ("US:MSFT", "마이크로소프트", ("마이크로소프트", "Microsoft")),
    "MU": ("US:MU", "마이크론 테크놀로지", ("마이크론 테크놀로지", "Micron Technology")),
    "META": ("US:META", "메타", ("메타", "Meta Platforms")),
    "AVGO": ("US:AVGO", "브로드컴", ("브로드컴", "Broadcom")),
    "TSLA": ("US:TSLA", "테슬라", ("테슬라", "Tesla")),
    "INTC": ("US:INTC", "인텔", ("인텔", "Intel")),
    "SNDK": ("US:SNDK", "샌디스크", ("샌디스크", "Sandisk")),
    "CRWV": ("US:CRWV", "코어위브", ("코어위브", "CoreWeave")),
    "ORCL": ("US:ORCL", "오라클", ("오라클", "Oracle")),
    "LLY": ("US:LLY", "일라이 릴리", ("일라이 릴리", "Eli Lilly")),
    "IREN": ("US:IREN", "아이렌", ("아이렌", "IREN")),
    "IONQ": ("US:IONQ", "아이온큐", ("아이온큐", "IonQ")),
    "MRNA": ("US:MRNA", "모더나", ("모더나", "Moderna")),
}
_NEWS_SNAPSHOT_LABELS = {
    "US:ALPHABET": ("알파벳", "알파벳 Class A", "알파벳 Class C"),
    "US:TSM": ("TSMC", "TSMC ADR"),
    "US:AMZN": ("아마존", "아마존닷컴"),
    "US:PLTR": ("팔란티어", "팔란티어 테크놀로지스"),
    "US:MRVL": ("마벨 테크놀로지 그룹", "마벨"),
}


def normalize_us_ticker(symbol):
    """Remove only verified Naver Reuters market suffixes, preserving share class."""
    symbol = str(symbol or "").strip().upper()
    if symbol.endswith((".O", ".N")):
        symbol = symbol[:-2]
    return symbol if re.fullmatch(r"[A-Z0-9]+(?:\.[A-Z])?", symbol) else ""


def resolve_us_identity(name, symbol=None):
    """Return strict match or an independent pending identity.

    No ticker + exact known display label is safe only for one registered name.
    Distinct tickers with overlapping names cannot be joined without the code.
    """
    original = str(name or "").strip()
    raw_symbol = str(symbol or "").strip().upper()
    ticker = normalize_us_ticker(symbol)
    if ticker and ticker in _VERIFIED:
        key, canonical, aliases = _VERIFIED[ticker]
        if original.casefold() in {x.casefold() for x in aliases}:
            return {"company_key": key, "news_name": canonical,
                    "status": "verified", "ticker": ticker}
    if not ticker:
        matched = {(key, canonical)
                   for key, canonical, aliases in _VERIFIED.values()
                   if original.casefold() in {x.casefold() for x in aliases}}
        if len(matched) == 1:
            key, canonical = next(iter(matched))
            return {"company_key": key, "news_name": canonical,
                    "status": "verified", "ticker": ""}
    # A new name/ticker is never silently merged into an existing company.
    return {"company_key": "US:" + (ticker or raw_symbol or original),
            "news_name": original, "status": "pending", "ticker": ticker}


def news_snapshot_names(name, symbol=None):
    """Bounded, deduplicated fallback keys; no cross-company company-name joins."""
    original = str(name or "").strip()
    identity = resolve_us_identity(original, symbol)
    candidates = [original]
    if identity["status"] == "verified":
        candidates.append(identity["news_name"])
        candidates.extend(_NEWS_SNAPSHOT_LABELS.get(identity["company_key"], ()))
    return list(dict.fromkeys(value for value in candidates if value))
