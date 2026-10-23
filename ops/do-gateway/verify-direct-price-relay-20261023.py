"""Read-only verification of DO -> Render in-memory quote relay, no credentials."""
import json
import requests
url="https://gaemi-gtp.onrender.com/health"
try:
    r=requests.get(url, timeout=12, allow_redirects=False)
    print("RELAY_HEALTH_HTTP="+str(r.status_code),flush=True)
    data=r.json() if r.status_code==200 else {}
    feed=data.get("us_live_feed") if isinstance(data,dict) else None
    if isinstance(feed,dict):
        count=feed.get("fresh_symbols")
        print("RELAY_HEALTH_FRESH_SYMBOLS="+str(count),flush=True)
        print("RELAY_HEALTH_RECEIVING="+str(feed.get("receiving")),flush=True)
        assert isinstance(count,int) and count>0, "no_fresh_prices"
        print("RELAY_HEALTH_VERIFIED",flush=True)
    else:
        print("RELAY_HEALTH_FIELD_NOT_DEPLOYED",flush=True)
        raise SystemExit(4)
except Exception as exc:
    print("RELAY_HEALTH_CHECK_ERROR="+type(exc).__name__,flush=True)
    raise SystemExit(2)
