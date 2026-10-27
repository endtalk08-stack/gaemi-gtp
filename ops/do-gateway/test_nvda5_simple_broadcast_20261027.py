"""One isolated latest-five Nvidia body/input test, max one model1 call. No production writes."""
import sys,os,json,time,re,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,'/opt/gaemigtp-news/app')
sys.path.insert(0,'/opt/gaemigtp-news/app/ops')
from backend.services import news_feed
from backend.services.news_detail import read_selected_article_details
from staged_daily_groq_issues import _article_published_epoch
def out(k,v): print(k+'='+json.dumps(v,ensure_ascii=False),flush=True)
raw=news_feed.fetch_stock_news('엔비디아',market='미국',limit=50,raise_on_error=True)
rows=sorted((a for a in raw if isinstance(a,dict)),key=_article_published_epoch,reverse=True)[:5]
out('LATEST_COUNT',len(rows))
details=read_selected_article_details(rows,limit=5,with_sources=True)
news=[]; verified=0
for i,(a,d) in enumerate(zip(rows,details),1):
 text=str(d.get('text') or '').strip(); kind=d.get('source')
 good=kind in ('jsonld_article_body','article_or_main_paragraphs') and len(text)>=500
 verified+=int(good)
 description=str(a.get('description') or a.get('summary') or '')
 used=text if good else description
 out('ARTICLE',{'id':i,'title':a.get('title'),'url':a.get('url') or a.get('link'),'published':a.get('pubDate') or a.get('published_at'),'description_chars':len(description),'extract_source':kind,'extracted_chars':len(text),'body_accepted':good,'sent_chars':len(used),'input_type':'extracted_body_max5000' if good else 'api_description'})
 news.append({'id':i,'title':a.get('title'),'published':a.get('pubDate') or a.get('published_at'),'input_type':'article_body' if good else 'api_description','content':used})
out('VERIFIED_BODY_COUNT',verified)
prompt='엔비디아의 최근 이슈는 뭐야? 방송용으로 제목과 내용을 작성해줘.'
out('PROMPT',prompt)
messages=[{'role':'user','content':prompt+'\n'+json.dumps({'stock':'엔비디아','news':news},ensure_ascii=False)}]
out('INPUT_CHARS',len(messages[0]['content']))
key=os.environ.get('GROQ_API_KEY','').strip()
if not key:
 p=Path('/opt/gaemigtp-news/app/ops/.groq_api_key')
 if p.is_file(): key=p.read_text().strip()
if not key:
 out('NO_CALL','missing_key');sys.exit(0)
payload={'model':'openai/gpt-oss-20b','messages':messages,'temperature':0.2,'reasoning_effort':'low','max_completion_tokens':1800}
out('MAX_CALLS',1)
req=urllib.request.Request('https://api.groq.com/openai/v1/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'gaemiGTP-ai-test/1.0'})
start=time.monotonic()
try:
 with urllib.request.urlopen(req,timeout=55) as resp:
  obj=json.load(resp)
  out('RATE_HEADERS',{k:v for k,v in resp.headers.items() if k.lower().startswith('x-ratelimit')})
 out('USAGE',obj.get('usage'))
 choice=(obj.get('choices') or [{}])[0]
 out('FINISH_REASON',choice.get('finish_reason'))
 answer=(choice.get('message') or {}).get('content') or ''
 out('ANSWER',answer)
 out('ANSWER_CHARS',len(answer))
except urllib.error.HTTPError as e:
 out('HTTP_STATUS',e.code)
 out('RATE_HEADERS',{k:v for k,v in e.headers.items() if k.lower().startswith('x-ratelimit') or k.lower()=='retry-after'})
 try:
  error=json.loads(e.read(12000)).get('error',{})
  msg=str(error.get('message') or '').replace(key,'[REDACTED]')
  out('PROVIDER_ERROR',{'type':error.get('type'),'code':error.get('code'),'message':msg[:1500]})
 except Exception: out('PROVIDER_ERROR','non_json_error')
except Exception as e: out('FAILURE_TYPE',type(e).__name__)
out('ELAPSED_SECONDS',round(time.monotonic()-start,2))
out('ISOLATED_TEST_DONE',True)
