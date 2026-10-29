"""Read-only selection of existing verified US TOP20 results.

No Naver ranking requests, quote reads, or industry enrichment on Render.
"""
import re
import threading
import time



# These are the existing processed menu results, retained for central-chat
# selection. AI lookups never trigger Naver collection.
_MARKET_RESULTS = {}
_MARKET_RESULTS_LOCK = threading.Lock()
_SELECTION_TTL = 15 * 60


def _remember_market_result(market, menu, rows):
    with _MARKET_RESULTS_LOCK:
        _MARKET_RESULTS[(market, menu)] = (
            time.monotonic(), [dict(row) for row in rows],
        )


def get_market_selection(market, menu, symbol, stock=None):
    """Read one previously produced menu row by stock code, without collection."""
    if market != "us" or menu != "value":
        return None
    code = str(symbol or "").strip().upper()
    pattern = r"[A-Z0-9.^_-]{1,32}"
    if not re.fullmatch(pattern, code):
        return None
    with _MARKET_RESULTS_LOCK:
        stored = _MARKET_RESULTS.get((market, menu))
        if not stored or time.monotonic() - stored[0] >= _SELECTION_TTL:
            return None
        match = next((r for r in stored[1] if r["symbol"].upper() == code), None)
        if not match:
            return None
        row = dict(match)
    if stock is not None and row["name"].casefold() != str(stock).strip().casefold():
        return None
    return {**row, "market": market, "menu": menu, "currency": "USD"}


def get_market_menu_rows(market, menu, sort="source"):
    """Read previously produced rows in the same order as the sidebar."""
    if market != "us" or menu != "value":
        return []
    with _MARKET_RESULTS_LOCK:
        stored = _MARKET_RESULTS.get((market, menu))
        if not stored or time.monotonic() - stored[0] >= _SELECTION_TTL:
            return []
        rows = [dict(row) for row in stored[1]]
    if sort == "change_pct":
        rows.sort(key=lambda row: -(
            row["change_pct"] if isinstance(row.get("change_pct"), (float, int))
            else float("-inf")
        ))
    for index, row in enumerate(rows):
        row["display_rank"] = index + 1 if sort == "change_pct" else row.get("rank")
        row["sort"] = "change_pct" if sort == "change_pct" else "source"
    return rows


def analysis_ticker_for_selection(selection):
    """Use a source-verified code and market to avoid name-based misrouting."""
    if not selection:
        return None
    symbol = str(selection.get("analysis_symbol") or selection["symbol"]).upper()
    if not re.fullmatch(r"[A-Z0-9.^_-]{1,32}", symbol):
        return None
    if not selection.get("analysis_symbol") and symbol.endswith((".O", ".N")):
        return symbol[:-2]
    return symbol
