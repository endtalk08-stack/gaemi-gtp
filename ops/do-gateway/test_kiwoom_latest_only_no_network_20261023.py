"""Dry-run check of deployed Kiwoom US one-snapshot collector and FE SQL.

All network and database IO mocked. No actual writes or market API calls.
"""
import datetime as std_datetime
import sys
import types
from unittest import mock
sys.path.insert(0, "/opt/gaemigtp-news/app")

from backend import kiwoom_us_value_collector as collector
from backend import kiwoom_us_live_prices as feeder

class FakeNow(std_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026,10,23,10,0,0,tzinfo=tz)

class Cursor:
    def __init__(self):
        self.queries=[]
        self.last=""
        self.rowcount=1
    def __enter__(self): return self
    def __exit__(self,*_): return False
    def execute(self, sql, args=None):
        self.last=sql
        self.queries.append((sql, args))
    def fetchone(self):
        return (1,) if "SELECT id FROM public.market_rank_snapshots" in self.last else None
    def fetchall(self): return []

class Connection:
    def __init__(self): self.cursor_obj=Cursor()
    def __enter__(self): return self
    def __exit__(self,*_): return False
    def cursor(self): return self.cursor_obj
    def commit(self): pass

def board_rows():
    return [{
        "rank":i,"symbol":"T"+str(i),"name":"Ticker "+str(i),
        "exchange":"ND","english_name":"Test "+str(i),
        "price":100.0+i,"change_pct":1.0,"trading_value":1000*i,
        "volume":i*100,"trading_value_raw":i
    } for i in range(1,21)]

con=Connection()
fake_dt=types.SimpleNamespace(datetime=FakeNow,timezone=std_datetime.timezone,time=std_datetime.time)
with mock.patch.dict("os.environ",{"NEWS_DATABASE_URL":"mocked://no-network"}):
    with mock.patch.object(collector,"dt",fake_dt):
        with mock.patch.object(collector,"fetch_us_trading_value_top",side_effect=lambda limit: board_rows()):
            with mock.patch.object(collector,"_fill_missing_us_industries"):
                with mock.patch("psycopg.connect",return_value=con):
                    assert collector.main()==0
sqls=[sql for sql,_ in con.cursor_obj.queries]
assert sum("UPDATE public.market_rank_snapshots" in sql for sql in sqls)==1
assert sum("INSERT INTO public.market_rank_entries" in sql for sql in sqls)==20
assert sum("INSERT INTO public.market_rank_snapshots" in sql for sql in sqls)==0
assert not any("DELETE " in sql for sql in sqls)
print("LATEST_ONLY_COLLECTOR_DRYRUN_PASS one_existing_snapshot_twenty_upserts_no_delete",flush=True)

fecon=Connection()
with mock.patch("psycopg.connect",return_value=fecon):
    n=feeder._persist("mocked://no-network",{"NVDA":(210.5,2.1)})
assert n==1
updates=[sql for sql,_ in fecon.cursor_obj.queries if "UPDATE public.market_rank_entries" in sql]
assert len(updates)==1 and "IS DISTINCT FROM" in updates[0]
assert len(fecon.cursor_obj.queries[-1][1])==8
print("LATEST_ONLY_FE_DRYRUN_PASS changed_values_only_and_no_history_insert",flush=True)
