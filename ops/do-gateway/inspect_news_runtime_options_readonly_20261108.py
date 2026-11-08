"""Read-only checks of service environment options without revealing credentials."""
import pathlib, subprocess
env_path=pathlib.Path("/etc/gaemigtp/news-worker.env")
keys=("TRADINGVIEW_NEWS_MODE","TRADINGVIEW_NEWS_FOUR_FEEDS_ENABLED","NEWS_DETAIL_REQUEST_BUDGET","NEWS_DETAIL_PUBLICATION_ALLOWED","TRADINGVIEW_API_KEY")
try:
 readable=env_path.is_file() and env_path.stat().st_size<50000 and __import__("os").access(env_path,__import__("os").R_OK)
except PermissionError:
 readable=False
print("NEWS_RUNTIME_ENV_READABLE="+str(readable))
values={}
if readable:
 for line in env_path.read_text(encoding="utf-8").splitlines():
  line=line.strip()
  if not line or line.startswith("#") or "=" not in line:continue
  k,v=line.split("=",1)
  k=k.strip()
  if k in keys:values[k]=v.strip().strip('"').strip("'")
for k in keys:
 print("RUNTIME_SETTING_"+k+"_PRESENT="+str(k in values))
 if k in keys[:4]:
  value=values.get(k)
  if value is not None:print("RUNTIME_SETTING_"+k+"_VALUE="+str(value[:35]))
for unit in ("gaemigtp-news.service","gaemigtp-tradingview-news.service"):
 p=subprocess.run(["systemctl","is-active",unit],capture_output=True,text=True)
 print("RUNTIME_UNIT="+unit+" ACTIVE="+p.stdout.strip())
print("NEWS_RUNTIME_OPTIONS_INSPECT_OK=1")
