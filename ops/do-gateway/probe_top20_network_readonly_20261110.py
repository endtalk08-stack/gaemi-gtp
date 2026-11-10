"""Read-only network and HTTPS probe for existing DigitalOcean TOP20 endpoint."""
import socket, ssl, urllib.error, urllib.request, json
from pathlib import Path

def tcp(name,host,port):
    try:
        s=socket.create_connection((host,port),timeout=5)
        print("NETWORK_TCP",name,"ok",flush=True)
        s.close()
    except Exception as e: print("NETWORK_TCP",name,type(e).__name__,flush=True)

for name,host,port in [
 ("loopback_tls","127.0.0.1",443),
 ("public_ip_tls","168.144.131.211",443),
 ("local_api","127.0.0.1",8765),
 ("cloudflare_dns","quotes.gaemigtp.com",443),
]: tcp(name,host,port)

for name,url,context in [
 ("local_tls","https://127.0.0.1/health",ssl._create_unverified_context()),
 ("public_ip","https://168.144.131.211/health",ssl._create_unverified_context()),
 ("cf_quotes","https://quotes.gaemigtp.com/health",ssl.create_default_context()),
 ("pages","https://gaemigtp-news.pages.dev/",ssl.create_default_context()),
 ("pages_news","https://gaemigtp-news.pages.dev/news/latest.json",ssl.create_default_context()),
]:
    try:
        with urllib.request.urlopen(url,context=context,timeout=8) as r:
            body=r.read(100)
            print("NETWORK_HTTP",name,"status",r.status,"type",r.headers.get("Content-Type","")[:32],flush=True)
    except urllib.error.HTTPError as e: print("NETWORK_HTTP",name,"HTTP",e.code,flush=True)
    except Exception as e: print("NETWORK_HTTP",name,type(e).__name__,str(e)[:120],flush=True)
