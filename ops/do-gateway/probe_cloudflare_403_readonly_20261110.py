"""Inspect bounded Cloudflare error body only; no credentials, no user data."""
import urllib.request,urllib.error
for name,url in [("quotes","https://quotes.gaemigtp.com/health"),("pages","https://gaemigtp-news.pages.dev/")]:
 try:
  with urllib.request.urlopen(url,timeout=7) as r:print("EDGE",name,r.status,flush=True)
 except urllib.error.HTTPError as e:
  body=e.read(240).decode("utf-8","replace")
  print("EDGE",name,e.code,"body",repr(body),"server",e.headers.get("server"),
        "ray",e.headers.get("cf-ray"),flush=True)
 except Exception as e:print("EDGE",name,type(e).__name__,flush=True)
