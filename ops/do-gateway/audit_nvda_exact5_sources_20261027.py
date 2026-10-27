"""Read only the five test source articles. No AI calls, no production edits."""
import sys,json,re
sys.path.insert(0,'/opt/gaemigtp-news/app')
from backend.services import news_feed
from backend.services.news_detail import read_selected_article_details
urls=['https://www.pinpointnews.co.kr/news/articleView.html?idxno=498789','http://www.metroseoul.co.kr/article/20261027500444','http://www.finomy.com/news/articleView.html?idxno=264738','https://www.news2day.co.kr/article/20261027500198','http://www.inews24.com/view/2019142']
raw=news_feed.fetch_stock_news('엔비디아',market='미국',limit=50,raise_on_error=True)
items=[]
for url in urls:
 a=next((a for a in raw if (a.get('url') or a.get('link'))==url),{'url':url})
 items.append(a)
details=read_selected_article_details(items,limit=5,with_sources=True)
for i,(a,d) in enumerate(zip(items,details),1):
 body=d.get('text') or ''
 print('SOURCE='+json.dumps({'id':i,'url':urls[i-1],'title':a.get('title'),'description':a.get('description'),'kind':d.get('source'),'chars':len(body)},ensure_ascii=False),flush=True)
 for term in ['엔비디아','11월','30일','DSX','HBM3E','루빈','하락','30%','메모리 개발','인증','공급망']:
  snippets=[]
  for m in list(re.finditer(re.escape(term),body,re.I))[:8]:
   snippets.append(body[max(0,m.start()-120):min(len(body),m.end()+220)])
  if snippets:print('EVIDENCE='+json.dumps({'id':i,'term':term,'snippets':snippets},ensure_ascii=False),flush=True)
print('SOURCE_AUDIT_NO_AI_DONE',flush=True)
