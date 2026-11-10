"""Read-only production Pages checks after unified TOP20 deployment."""
import urllib.request,urllib.error,json,re,hashlib
base='https://gaemigtp-news.pages.dev'
headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36','Accept':'application/json, text/html;q=0.9'}
for label,path in [('homepage','/'),('top20','/market/trading-value?market=us'),('news','/news/latest.json')]:
 try:
  req=urllib.request.Request(base+path,headers=headers)
  with urllib.request.urlopen(req,timeout=20) as r:
   body=r.read(220000)
   print('PAGE',label,'HTTP',r.status,'bytes',len(body),'type',r.headers.get('Content-Type',''),flush=True)
   if label=='homepage':
    text=body.decode('utf-8','replace')
    print('PAGE_UI_TOP20_PANEL',('usTop20Panel' in text),'NEWS_LIST',('newsList' in text),
          'R2_PATH',('/news/latest.json' in text),'OLD_NEWS_STYLES',('.news-title{font-size:16px' in text),flush=True)
   else:
    data=json.loads(body)
    items=data.get('items')
    print('PAGE_JSON',label,'ok',data.get('ok'),'rows',len(items) if isinstance(items,list) else None,
         'source',data.get('source'),'error',data.get('error'),flush=True)
 except urllib.error.HTTPError as e:
  print('PAGE',label,'HTTP_ERROR',e.code,repr(e.read(120).decode('utf-8','replace')),flush=True)
 except Exception as e:
  print('PAGE',label,'ERROR',type(e).__name__,str(e)[:130],flush=True)
