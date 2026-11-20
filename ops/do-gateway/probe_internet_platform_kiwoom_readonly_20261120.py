"""Verify the approved three-company group with one existing Kiwoom ranking read."""
import json
import math
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path.cwd()))

from backend.providers.kiwoom_us_industries import fetch_us_industry_stocks as read_market_cap_ranking
from backend.providers.kiwoom_us_quotes import KiwoomReadOnlyError

observed = []


def fetch_us_industry_stocks(industry, sort):
    ranking = read_market_cap_ranking(industry, sort)
    for row in ranking["items"]:
        ticker = row["symbol"].removesuffix(".O")
        if ticker in {"GOOG", "GOOGL", "META", "NFLX"}:
            observed.append({
                "symbol": ticker,
                "exchange": row["exchange"],
                "change_pct": row["change_pct"],
                "market_cap_usd": row["market_cap_usd"],
            })
    return ranking


def fetch_us_internet_platform_group():
    """Average the three approved issuers using Kiwoom market-cap ranking data."""
    # In Kiwoom's catalog 370 is Media. Only the approved issuers count
    # toward this representative group, and Alphabet counts once.
    aliases_by_issuer = (("GOOG", "GOOGL"), ("META",), ("NFLX",))
    allowed_symbols = {symbol for aliases in aliases_by_issuer for symbol in aliases}
    ranking = fetch_us_industry_stocks("370", "marketcap")
    by_symbol = {}
    for row in ranking["items"]:
        symbol = row["symbol"].removesuffix(".O")
        if symbol in allowed_symbols and row["exchange"] == "ND":
            by_symbol.setdefault(symbol, {**row, "symbol": symbol})

    members = []
    for aliases in aliases_by_issuer:
        representative = next((
            by_symbol[symbol] for symbol in aliases
            if symbol in by_symbol and by_symbol[symbol]["change_pct"] is not None
        ), None)
        if representative is None:
            return None
        members.append(representative)

    leaders = sorted(members, key=lambda item: item["market_cap_usd"], reverse=True)[:2]
    return {
        "display_name": "인터넷플랫폼 대표 종목군",
        "description": "알파벳·메타·넷플릭스 3개 기업의 등락률 평균",
        "change_pct": math.fsum(member["change_pct"] for member in members) / len(members),
        "change_method": "equal_weighted_representative_company_returns",
        "mapping_status": "matched",
        "source": ranking["source"],
        "fetched_at": ranking["fetched_at"],
        "member_symbols": [member["symbol"] for member in members],
        "stocks": [{**row, "rank": rank} for rank, row in enumerate(leaders, 1)],
    }


def main():
    try:
        group = fetch_us_internet_platform_group()
    except KiwoomReadOnlyError as exc:
        error = str(exc)
        if not re.fullmatch(r"kiwoom_[a-z0-9_]{1,120}", error):
            error = type(exc).__name__
        print("KIWOOM_PLATFORM_VERIFICATION=" + json.dumps({"ok": False, "error": error}), flush=True)
        return 2
    report = {"ok": group is not None, "source": "kiwoom:usa20550", "industry_code": "370", "observed": observed}
    if group is not None:
        report.update(
            fetched_at=group["fetched_at"],
            members=group["member_symbols"],
            change_pct=group["change_pct"],
            leaders=[row["symbol"] for row in group["stocks"]],
        )
    print("KIWOOM_PLATFORM_VERIFICATION=" + json.dumps(report, allow_nan=False), flush=True)
    return 0 if group is not None else 3


if __name__ == "__main__":
    raise SystemExit(main())
