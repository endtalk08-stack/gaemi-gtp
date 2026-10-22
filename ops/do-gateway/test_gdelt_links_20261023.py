"""Read-only GDELT link metadata availability test; no writes or secrets."""
import json, urllib.request, urllib.parse
q='"Nvidia" sourcelang:english'
params={"query":q,"mode":"artlist","format":"json","timespan":"24h","maxrecords":5,"sort":"datedesc"}
url="https://api.gdeltproject.org/api/v2/doc/doc?"+urllib.parse.urlencode(params)
req=urllib.request.Request(url,headers={"User-Agent":"gaemiGTP/1.0 (public source link check)","Accept":"application/json"})
try:
  with urllib.request.urlopen(req,timeout=18) as resp:
    raw=resp.read(120000)
    print("STATUS",resp.status,"CONTENT_TYPE",resp.headers.get("Content-Type"),"SIZE",len(raw))
  data=json.loads(raw)
  rows=data.get("articles",[])
  print("ARTICLE_COUNT",len(rows))
  for item in rows[:5]:
    print("NEWS",json.dumps({"title":item.get("title"),"url":item.get("url"),"domain":item.get("domain"),"language":item.get("language"),"seendate":item.get("seendate")},ensure_ascii=False))
except Exception as exc:
  print("API_ERROR",type(exc).__name__,str(exc)[:220])
