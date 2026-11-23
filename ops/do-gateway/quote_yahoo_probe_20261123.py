import datetime as dt
import json
import urllib.request
from zoneinfo import ZoneInfo
for ticker in ('QQQ','NVDA','XLK'):
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+ticker+'?range=10d&interval=1d'
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=9) as response:
            data=json.load(response)['chart']['result'][0]
        meta=data['meta']; prices=data['indicators']['quote'][0]['close']
        rows=[(dt.datetime.fromtimestamp(ts,ZoneInfo('America/New_York')).date().isoformat(),close)
              for ts,close in zip(data['timestamp'],prices)]
        print(ticker,meta.get('symbol'),meta.get('currency'),meta.get('exchangeTimezoneName'),rows[-3:],flush=True)
    except Exception as error:
        print(ticker,type(error).__name__,flush=True)
