"""Check existing shared Naver sector data for two Kiwoom-missing US tickers.
Read-only; do not create rankings, query AI, or write Neon.
"""
from backend.providers.market_industry import get_stock_industries

for codes in (["SPCX.O","SNDK.O"],["SPCX","SNDK"]):
    try:
        sectors=get_stock_industries("us",codes)
        print("US_INDUSTRY_PROBE="+repr({"codes":codes,"labels":sectors}),flush=True)
    except Exception as exc:
        print("US_INDUSTRY_PROBE_ERROR="+type(exc).__name__,flush=True)
