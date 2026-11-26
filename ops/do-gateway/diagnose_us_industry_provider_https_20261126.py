"""Read-only live Kiwoom provider diagnosis using the credentialed HTTPS service environment."""
import json, os, pathlib, subprocess, sys
APP=pathlib.Path("/opt/gaemigtp-news/app")
sys.path.insert(0,str(APP))
def cmd(args):
 p=subprocess.run(args,text=True,capture_output=True,timeout=10)
 return (p.stdout or "").strip()
def main():
 for unit in ("gaemigtp-kiwoom-us-top20-api.service","gaemigtp-kiwoom-us-top20-https.service"):
  pid=cmd(["systemctl","show",unit,"-p","MainPID","--value"])
  print("UNIT_PID",unit,pid,flush=True)
  if unit.endswith("-https.service"):
   try:
    for item in pathlib.Path("/proc",pid,"environ").read_bytes().split(b"\\0"):
     if item.startswith((b"GAEMI_KIWOOM_APP_KEY=",b"GAEMI_KIWOOM_APP_SECRET=")):
      k,v=item.split(b"=",1); os.environ[k.decode()]=v.decode()
   except Exception as e: print("ENV_READ_ERROR",type(e).__name__,flush=True)
 print("CREDENTIALS_CONFIGURED",bool(os.environ.get("GAEMI_KIWOOM_APP_KEY") and os.environ.get("GAEMI_KIWOOM_APP_SECRET")),flush=True)
 try:
  from backend.providers import kiwoom_us_industries as p
  token=p._access_token()
  a=p._call("usa10101",{"gubun":"1"},token=token)
  b=p._call("usa23000",{"stex_tp":"0","inds_cd":"0"},token=token)
  def info(rows):
   if not isinstance(rows,list): return {"type":type(rows).__name__}
   row=next((x for x in rows if isinstance(x,dict)),{})
   return {"count":len(rows),"keys":sorted(row.keys()),"inds_cd":row.get("inds_cd"),"perf_1d":row.get("perf_1d")}
  print("USA10101",json.dumps(info(a.get("list")),ensure_ascii=False),flush=True)
  print("USA23000",json.dumps(info(b.get("result_list")),ensure_ascii=False),flush=True)
  if isinstance(a.get("list"),list) and isinstance(b.get("result_list"),list):
   built=p._build_us_industry_map(a["list"],b["result_list"],p.INDUSTRY_GROUPS)
   print("BUILT",json.dumps({"fetched_at":built.get("fetched_at"),"items":[{"key":x.get("key"),"change_pct":x.get("change_pct"),"mapping_status":x.get("mapping_status")} for x in built.get("items",[])]},ensure_ascii=False),flush=True)
 except Exception as e:
  m=str(e); safe=m if len(m)<100 and all(c.isalnum() or c in "_-" for c in m) else type(e).__name__
  print("PROVIDER_ERROR",type(e).__name__,safe,flush=True)
if __name__=="__main__": main()
