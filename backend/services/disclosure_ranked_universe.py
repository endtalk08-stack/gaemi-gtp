"""Verified DART/SEC identity registry for the disclosure collector.

News and disclosures use the existing verified stock-code / company-ID
mapping. Never fetch popularity, trading-value, live quotes, or new
rankings to decide which companies have filings.
"""
import re


def resolve_universe(engine):
    """Return verified known company identifiers without external API calls."""
    korean = getattr(engine, "DART_STOCK_CORP_CODES", {})
    american = getattr(engine, "US_CIKS", {})
    return {
        "KR": sorted(
            code for code, corp in korean.items()
            if re.fullmatch(r"[0-9]{6}", str(code))
            and re.fullmatch(r"[0-9]{8}", str(corp))
        ),
        "US": sorted(
            symbol for symbol, cik in american.items()
            if re.fullmatch(r"[A-Z.]{1,10}", str(symbol))
            and re.fullmatch(r"[0-9]{10}", str(cik))
        ),
    }
