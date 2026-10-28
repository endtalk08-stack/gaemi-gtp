"""Offline regressions: no external provider or database is contacted."""
import os,sys,types,unittest,importlib.util,datetime as dt
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
ROOT=Path(os.getenv('MARKET_TEST_ROOT','/opt/gaemigtp-news/app'))
sys.path.insert(0,str(ROOT))
from backend.services.market_data_cache import MarketReadCache,cached_market_json
from backend.services import kiwoom_us_value_board as board

def load_collector():
    provider=types.ModuleType('backend.providers.kiwoom_us_quotes')
    provider.fetch_us_daily_chart=lambda *a,**kw: (_ for _ in ()).throw(AssertionError('external API forbidden'))
    provider.issue_access_token=provider.fetch_us_daily_chart
    pg=types.ModuleType('psycopg');pg.connect=lambda *a,**kw: (_ for _ in ()).throw(AssertionError('DB forbidden'))
    spec=importlib.util.spec_from_file_location('cost_daily',ROOT/'backend/kiwoom_us_daily_collector.py')
    module=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'psycopg':pg,'backend.providers.kiwoom_us_quotes':provider}):spec.loader.exec_module(module)
    return module

class Controls(unittest.TestCase):
    def test_concurrent_visitors_share_one_read(self):
        cache=MarketReadCache();calls=[]
        def load():calls.append(1);return {'rows':[1]}
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:cache.get_or_load('same',load,ttl=60),range(20)))
        self.assertEqual(len(calls),1);results[0]['rows'].append(2)
        self.assertEqual(cache.get_or_load('same',load,ttl=60),{'rows':[1]})
    def test_cache_expires_and_is_bounded(self):
        cache=MarketReadCache(2)
        with patch('backend.services.market_data_cache.time.monotonic',return_value=100):cache.get_or_load('a',lambda:1,ttl=5)
        with patch('backend.services.market_data_cache.time.monotonic',return_value=106):self.assertEqual(cache.get_or_load('a',lambda:2,ttl=5),2)
        cache.get_or_load('b',lambda:3,ttl=5);cache.get_or_load('c',lambda:4,ttl=5)
        self.assertEqual(len(cache._entries),2)
    def test_empty_result_retry_is_short_and_not_per_visitor(self):
        cache=MarketReadCache();calls=[]
        def load():calls.append(1);return None
        with patch('backend.services.market_data_cache.time.monotonic',return_value=100):
            for _ in range(10):cache.get_or_load('a',load,ttl=60,empty_ttl=15)
        with patch('backend.services.market_data_cache.time.monotonic',return_value=116):cache.get_or_load('a',load,ttl=60,empty_ttl=15)
        self.assertEqual(len(calls),2)
    def test_rank_cache_isolation_from_live_price_overlay(self):
        board._BOARD_CACHE.clear()
        with patch.object(board,'_read_us_trading_value_board_uncached',return_value=[{'symbol':'A','price':1}]) as load:
            first=board.read_us_trading_value_board();first[0]['price']=99
            self.assertEqual(board.read_us_trading_value_board()[0]['price'],1);self.assertEqual(load.call_count,1)
    def test_invalid_rank_limit_does_not_touch_db(self):
        with patch.object(board,'_read_us_trading_value_board_uncached') as load:
            with self.assertRaises(ValueError):board.read_us_trading_value_board(100)
            load.assert_not_called()
    def test_short_ipo_history_uses_incremental_window(self):
        c=load_collector();today=dt.date(2026,10,28)
        self.assertEqual(c.history_start(today,today-dt.timedelta(days=1),8),today-dt.timedelta(days=5))
        self.assertEqual(c.history_start(today,None,0),today-dt.timedelta(days=180))
    def test_refresh_window_and_same_day_idempotency(self):
        c=load_collector();zone=ZoneInfo('America/New_York')
        self.assertFalse(c.refresh_window(dt.datetime(2026,10,28,10,tzinfo=zone)))
        self.assertTrue(c.refresh_window(dt.datetime(2026,10,28,16,20,tzinfo=zone)))
        self.assertFalse(c.refresh_window(dt.datetime(2026,10,31,17,tzinfo=zone)))
        now=dt.datetime(2026,10,28,17,20,tzinfo=zone)
        self.assertTrue(c.already_refreshed(now,now.date(),now-dt.timedelta(hours=1)))
        self.assertFalse(c.already_refreshed(now,now.date(),now-dt.timedelta(hours=2)))
    def test_new_rank_entry_and_reentry_bootstrap_only_missing_history(self):
        c=load_collector();zone=ZoneInfo('America/New_York')
        now=dt.datetime(2026,10,28,11,tzinfo=zone)
        self.assertTrue(c.needs_bootstrap(now,None))
        self.assertTrue(c.needs_bootstrap(now,dt.date(2026,10,23)))
        self.assertFalse(c.needs_bootstrap(now,dt.date(2026,10,27)))
        self.assertFalse(c.needs_bootstrap(now,dt.date(2026,10,28)))
        monday=dt.datetime(2026,11,2,10,tzinfo=zone)
        self.assertFalse(c.needs_bootstrap(monday,dt.date(2026,10,30)))

    def test_bootstrap_fetches_only_new_and_stale_reentries(self):
        c=load_collector();requests=[]
        class Clock(dt.datetime):
            @classmethod
            def now(cls,tz=None):return cls(2026,10,28,15,tzinfo=dt.timezone.utc)
        class Conn:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def cursor(self):return self
            def execute(self,*args):pass
            def commit(self):pass
            def fetchall(self):
                return [('OLD','ND',dt.date(2026,10,27),80,None),
                        ('NEW','NY',None,0,None),
                        ('RETURN','ND',dt.date(2026,10,20),70,None)]
        def fetch(symbol,exchange,start,**kwargs):
            requests.append((symbol,start))
            return {'ticker':symbol,'source':c.SOURCE,'rows':[{
                'date':'2026-10-27','open':10,'high':12,'low':9,'close':11,'volume':100}]}
        with patch.object(c.dt,'datetime',Clock),patch.object(c.psycopg,'connect',return_value=Conn()),patch.object(c,'issue_access_token',return_value='test'),patch.object(c,'fetch_us_daily_chart',side_effect=fetch),patch.object(c.time,'sleep'),patch.dict(os.environ,{'NEWS_DATABASE_URL':'offline-test'}):
            c.main(bootstrap=True)
        self.assertEqual([r[0] for r in requests],['NEW','RETURN'])
        self.assertEqual(requests[0][1],dt.date(2026,10,28)-dt.timedelta(days=180))
        self.assertEqual(requests[1][1],dt.date(2026,10,16))

    def test_off_hours_exits_before_database_connection(self):
        c=load_collector()
        class Clock(dt.datetime):
            @classmethod
            def now(cls,tz=None):return cls(2026,10,28,12,tzinfo=dt.timezone.utc)
        with patch.object(c.dt,'datetime',Clock):c.main()
    def test_pending_chart_result_is_retried_after_short_cache(self):
        try:from flask import Flask,jsonify
        except ImportError:self.skipTest('Flask checked on deployed runtime')
        app=Flask(__name__);loads=[]
        @app.get('/pending')
        @cached_market_json(ttl=300,error_ttl=15)
        def pending():
            loads.append(1)
            return jsonify({'ok':False,'rows':[]})
        with app.test_client() as client:
            with patch('backend.services.market_data_cache.time.monotonic',return_value=100):client.get('/pending')
            with patch('backend.services.market_data_cache.time.monotonic',return_value=110):client.get('/pending')
            self.assertEqual(len(loads),1)
            with patch('backend.services.market_data_cache.time.monotonic',return_value=116):client.get('/pending')
        self.assertEqual(len(loads),2)

    def test_shared_http_cache_keeps_access_hooks_and_symbol_separation(self):
        try:from flask import Flask,jsonify
        except ImportError:self.skipTest('Flask checked on deployed runtime')
        app=Flask(__name__);loads=[];access=[]
        @app.before_request
        def auth():access.append(1)
        @app.get('/chart')
        @cached_market_json(ttl=300,error_ttl=15)
        def chart():
            from flask import request
            symbol=request.args.get('symbol');loads.append(symbol)
            return jsonify({'rows':[symbol]})
        with app.test_client() as client:
            self.assertEqual(client.get('/chart?symbol=A').get_json(),{'rows':['A']})
            client.get('/chart?symbol=A');client.get('/chart?symbol=B')
        self.assertEqual(loads,['A','B']);self.assertEqual(len(access),3)
if __name__=='__main__':
    import subprocess
    chain=subprocess.run(['systemctl','show','gaemigtp-kiwoom-us-value.service','-p','OnSuccess','--value'],capture_output=True,text=True).stdout
    assert 'gaemigtp-kiwoom-us-chart-bootstrap.service' in chain
    for unit in ['gaemigtp-kiwoom-us-value.timer','gaemigtp-kiwoom-us-daily.timer','gaemigtp-kiwoom-us-fe.service','gaemigtp-news.service','gaemigtp-kiwoom-us-chart-bootstrap.service']:
        state=subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True).stdout.strip()
        assert state not in ('active','activating'), unit
        print('PAUSED_VERIFIED '+unit+' '+state,flush=True)
    print('RANK_SUCCESS_BOOTSTRAP_CHAIN_VERIFIED',flush=True)
    unittest.main()

