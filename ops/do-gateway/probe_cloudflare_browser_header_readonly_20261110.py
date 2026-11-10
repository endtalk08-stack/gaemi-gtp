"""Check if Cloudflare 1010 is limited to Python's default User-Agent."""
import urllib.request,urllib.error
urls=[("quotes","https://quotes.gaemigtp.com/market/trading-value?market=us"),
      ("pages","https://gaemigtp-news.pages.dev/news/latest.json")]
ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36"
for name,url in urls:
 for variant,agent in [("browser",ua),("generic","gaemigtp-news-top20-readonly-check/1.0")]:
  try:
   req=urllib.request.Request(url,headers={"User-Agent":agent,"Accept":"application/json"})
   with urllib.request.urlopen(req,timeout=9) as r:
    data=r.read(200000)
    print("PROBE",name,variant,r.status,"bytes",len(data),"type",r.headers.get("content-type"),flush=True)
  except urllib.error.HTTPError as e:
   print("PROBE",name,variant,e.code,"body",repr(e.read(90).decode("utf-8","replace")),flush=True)
  except Exception as e:print("PROBE",name,variant,type(e).__name__,flush=True)
