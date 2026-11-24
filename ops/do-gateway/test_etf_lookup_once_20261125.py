import json,time,hashlib
from pathlib import Path
from backend.providers.kiwoom_us_industries import ETF_TICKERS, fetch_us_etf_exchanges
print("ETF_TICKERS",sorted(ETF_TICKERS),flush=True)
try:
 t=time.monotonic()
 result=fetch_us_etf_exchanges()
 print("ETF_EXCHANGE_RESULT",json.dumps(result,sort_keys=True),flush=True)
 print("ETF_EXCHANGE_COUNT",len(result),"ELAPSED",round(time.monotonic()-t,2),flush=True)
except Exception as exc:
 print("ETF_EXCHANGE_ERROR",type(exc).__name__,repr(exc),flush=True)
