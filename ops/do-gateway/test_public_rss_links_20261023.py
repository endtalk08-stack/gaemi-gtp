"""Read-only public RSS link availability test from production DO."""
import json,urllib.request,urllib.parse,xml.etree.ElementTree as ET
feeds=[
  ("GoogleNewsUS","https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":"\"Nvidia\" when:1d","hl":"en-US","gl":"US","ceid":"US:en"})),
  ("CNBC","https://www.cnbc.com/id/10000664/device/rss/rss.html"),
]
for name,url in feeds:
  req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (gaemiGTP article links)","Accept":"application/rss+xml, application/xml, text/xml"})
  try:
    with urllib.request.urlopen(req,timeout=12) as r:
      blob=r.read(150000)
      print("STATUS",name,r.status,r.headers.get("Content-Type"))
    root=ET.fromstring(blob)
    items=root.findall(".//item")
    print("ITEM_COUNT",name,len(items))
    for item in items[:3]:
      print("NEWS",name,json.dumps({"title":item.findtext("title"),"link":item.findtext("link"),"source":item.findtext("source"),"pubDate":item.findtext("pubDate")},ensure_ascii=False))
  except Exception as exc:
    print("FAIL",name,type(exc).__name__,str(exc)[:150])
