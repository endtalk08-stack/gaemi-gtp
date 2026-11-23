import json
import urllib.request
for symbol in ('QQQ', 'NVDA', 'XLK'):
    url = 'https://gaemigtp-main.pages.dev/market/us-daily-chart?symbol=' + symbol
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'gaemi-quote-check/1.0'})
        with urllib.request.urlopen(req, timeout=9) as response:
            data = json.load(response)
        rows = data.get('rows') or []
        print(symbol, data.get('ok'), data.get('source'),
              [(row.get('date'),row.get('close')) for row in rows[-3:]], flush=True)
    except Exception as error:
        print(symbol, type(error).__name__, flush=True)
