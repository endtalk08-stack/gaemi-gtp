"""Read-only Kiwoom previous-close audit: 2026-11-20 NY session.
Print only ticker, public prices, dates, and safe error class. Never log tokens or raw responses.
"""
import datetime as dt
import sys
import time
from zoneinfo import ZoneInfo
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers import kiwoom_us_quotes as kiwoom
from backend import us_quote_change as yahoo

day=dt.date(2026,11,20)
symbols=(("QQQ","ND"),("NVDA","ND"),("SPY","NY"),("DIA","NY"),
         ("XLY","NY"),("XLC","NY"),("XLI","NY"),("XLB","NY"))
print("AUDIT_NY_NOW",dt.datetime.now(ZoneInfo("America/New_York")).isoformat(),flush=True)
print("AUDIT_SESSION",day.isoformat(),flush=True)
print("KIWOOM_CREDENTIALS_AVAILABLE",kiwoom.credentials_configured(),flush=True)
if not kiwoom.credentials_configured():
    print("AUDIT_BLOCKED_no_kiwoom_key_in_runner_environment",flush=True)
    sys.exit(0)

try:
    token=kiwoom.issue_access_token()
except Exception as exc:
    print("TOKEN_ISSUE_ERROR_CLASS",type(exc).__name__,flush=True)
    sys.exit(0)

for symbol,exchange in symbols:
    k_date=k_close=k_daily_change=None
    k_current=k_reference=k_live_change=None
    yahoo_close=yahoo_date=None
    try:
        result=kiwoom.fetch_us_close(symbol,exchange,day,token=token)
        if result is not None:
            k_date=result.get("session_date")
            k_close=result.get("close")
            k_daily_change=result.get("change_pct")
    except Exception as exc:
        print("KIWOOM_DAILY_ERROR",symbol,type(exc).__name__,str(exc)[:85] if str(exc).startswith("kiwoom_") else "",flush=True)
    try:
        q=kiwoom.fetch_us_quote(symbol,exchange,token=token)
        k_current=q.get("current")
        k_reference=q.get("previous_close")
        k_live_change=q.get("change_pct")
    except Exception as exc:
        print("KIWOOM_QUOTE_ERROR",symbol,type(exc).__name__,str(exc)[:85] if str(exc).startswith("kiwoom_") else "",flush=True)
    try:
        ref=yahoo._lookup(symbol,exchange,day,True)
        if ref is not None:
            yahoo_close,yahoo_date=ref
    except Exception as exc:
        print("YAHOO_ERROR_CLASS",symbol,type(exc).__name__,flush=True)
    cmp_daily=round(k_close-yahoo_close,5) if isinstance(k_close,(int,float)) and isinstance(yahoo_close,(int,float)) else None
    cmp_quote=round(k_reference-yahoo_close,5) if isinstance(k_reference,(int,float)) and isinstance(yahoo_close,(int,float)) else None
    computed=round((k_current/k_close-1)*100,3) if isinstance(k_current,(int,float)) and isinstance(k_close,(int,float)) and k_close else None
    print("COMPARE",symbol,"exchange",exchange,
          "kiwoom_daily_date",k_date,"kiwoom_daily_close",k_close,
          "kiwoom_daily_rate",k_daily_change,
          "kiwoom_live_price",k_current,"kiwoom_quote_base_close",k_reference,
          "kiwoom_vendor_rate",k_live_change,
          "yahoo_close_date",yahoo_date,"yahoo_close",yahoo_close,
          "daily_minus_yahoo",cmp_daily,"quote_base_minus_yahoo",cmp_quote,
          "computed_using_kiwoom_daily",computed,flush=True)
print("AUDIT_COMPLETE_READ_ONLY",flush=True)
