from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from backend.providers import tradingview_news

def ts(y,m,d,h,minute):
    ny=ZoneInfo("America/New_York")
    return datetime(y,m,d,h,minute,tzinfo=ny).timestamp()

cases=[
    ("premarket", ts(2026,11,6,8,30)),
    ("regular", ts(2026,11,6,12,30)),
    ("afterhours", ts(2026,11,6,16,30)),
    ("none", ts(2026,11,6,10,0)),
    ("weekend", ts(2026,11,7,12,30)),
]
for label,stamp in cases:
    slot,key=tradingview_news._basic_collection_slot(stamp)
    print(label, slot, key)
