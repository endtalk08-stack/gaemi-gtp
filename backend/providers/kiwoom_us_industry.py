"""Official Kiwoom usa10100 read-only US stock industry metadata.

Never access accounts, orders or private user endpoints. Only return the
industry when the returned exchange/symbol identifies the requested stock.
"""
import re
import requests
from backend.providers.kiwoom_us_quotes import issue_access_token, KiwoomReadOnlyError

_ENDPOINT = "https://api.kiwoom.com/api/us/stkinfo"
_EXCHANGES = frozenset(("ND", "NY", "NA"))

def fetch_us_stock_industry(symbol, exchange, *, token=None):
    code = str(symbol or "").strip().upper()
    market = str(exchange or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9.\\-]{1,20}", code) or market not in _EXCHANGES:
        return None
    access = token or issue_access_token()
    try:
        response = requests.post(
            _ENDPOINT,
            json={"stex_tp": market, "stk_cd": code},
            headers={"Content-Type": "application/json;charset=UTF-8",
                     "authorization": "Bearer " + access, "api-id": "usa10100"},
            timeout=3, allow_redirects=False,
        )
        if response.status_code != 200:
            return None
        data = response.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict) or str(data.get("return_code", 0)) not in ("0", "0000"):
        return None
    returned_symbol = str(data.get("stk_cd") or "").upper().strip()
    returned_market = str(data.get("stex_tp") or "").upper().strip()
    if returned_symbol != code or returned_market not in ("", market):
        return None
    name = data.get("upgb")
    if not isinstance(name, str):
        return None
    name = name.strip()
    if not name or len(name) > 120:
        return None
    return name
