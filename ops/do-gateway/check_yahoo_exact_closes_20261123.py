"""Read only external date close, no trading or Kiwoom credentials."""
import datetime as dt, sys
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.us_quote_change import _lookup
session=dt.date(2026,11,20)
for symbol,exchange in [("QQQ","ND"),("NVDA","ND"),("SPY","NY"),("DIA","NY"),
                        ("XLY","NY"),("XLC","NY"),("XLI","NY"),("XLB","NY")]:
    try:
        result=_lookup(symbol,exchange,session,True)
        print("YAHOO_EXACT_CLOSE",symbol,result,flush=True)
    except Exception as exc:
        print("YAHOO_CLOSE_ERROR",symbol,type(exc).__name__,flush=True)
print("YAHOO_EXACT_CLOSE_AUDIT_COMPLETE",flush=True)
