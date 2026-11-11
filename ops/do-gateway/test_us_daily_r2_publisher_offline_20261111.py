"""No-network check of chart serializer, R2 key, and read-only publisher."""
import sys
import datetime as dt
from decimal import Decimal
from unittest.mock import patch
from pathlib import Path
import json
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services import us_daily_r2_publisher as p
from backend.services import r2_news_uploader as u

rows=[(dt.date(2026,11,9),Decimal("100.12"),Decimal("105.1"),Decimal("99.01"),Decimal("102.55"),12345),
      (dt.date(2026,11,10),Decimal("102.5"),Decimal("110"),Decimal("101"),Decimal("109.23"),67890)]
d=p.make_chart("NVDA",rows)
assert d["count"]==2 and d["last_date"]=="2026-11-10"
assert d["first_date"]=="2026-11-09" and d["candles"][1]["close"]==109.23
try:
    p.make_chart("NVDA",rows[::-1])
    raise AssertionError("date validation failed")
except ValueError: pass
try:
    p.make_chart("../FOO",rows)
    raise AssertionError("symbol validation failed")
except ValueError: pass
assert u.re.fullmatch(r"(?:news/(?:stocks|ai)/us/[A-Z][A-Z0-9.-]{0,14}|charts/us/[A-Z][A-Z0-9.-]{0,14}/daily)\\.json","charts/us/NVDA/daily.json")
class Cur:
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql):assert "SELECT symbol,session_date" in sql and "INSERT" not in sql
    def fetchall(self):return [("NVDA",*row) for row in rows]
class Conn:
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def cursor(self):return Cur()
published=[]
def fake_upload(filepath, *, object_key):
    payload=json.loads(Path(filepath).read_text(encoding="utf-8"))
    assert object_key=="charts/us/NVDA/daily.json"
    assert payload["last_date"]=="2026-11-10" and payload["count"]==2
    published.append(object_key)
    return True
with patch.object(p.psycopg,"connect",return_value=Conn()),patch.object(p,"upload_file",side_effect=fake_upload),patch.dict(p.os.environ,{"R2_ACCESS_KEY_ID":"test","R2_SECRET_ACCESS_KEY":"test"}):
    result=p.publish_verified_top20("postgresql://unused")
assert result["uploaded"]==1 and result["failed"]==0 and published==["charts/us/NVDA/daily.json"]
print("US_DAILY_R2_OFFLINE=pass; no real DB writes or network calls")
