"""Read-only local listener and edge response headers for TOP20 debugging."""
import subprocess, urllib.request, urllib.error, ssl, socket
p=subprocess.run(["ss","-ltn"],capture_output=True,text=True,timeout=5)
print("LISTENER_LINES", flush=True)
for line in p.stdout.splitlines():
 if "443" in line or "8765" in line: print(line[:180],flush=True)
for label,url in [("quotes","https://quotes.gaemigtp.com/health"),("pages","https://gaemigtp-news.pages.dev/")]:
 try:
  with urllib.request.urlopen(url,timeout=7) as r:
   print("EDGE",label,r.status,r.headers.get("server"),r.headers.get("cf-ray"),flush=True)
 except urllib.error.HTTPError as e:
  print("EDGE",label,e.code,e.headers.get("server"),e.headers.get("cf-ray"),
        e.headers.get("content-type"),flush=True)
 except Exception as e:print("EDGE",label,type(e).__name__,flush=True)
