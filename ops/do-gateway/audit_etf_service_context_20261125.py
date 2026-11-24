import subprocess,re,os
unit="gaemigtp-kiwoom-us-top20-https.service"
for args in (["systemctl","show",unit,"-p","User","-p","MainPID","-p","ActiveState","-p","SubState","-p","ActiveEnterTimestamp","-p","EnvironmentFiles"],
             ["journalctl","-u",unit,"-n","220","--no-pager","-o","cat"]):
 r=subprocess.run(args,capture_output=True,text=True,timeout=12)
 print("CMD",args[0:3],"RC",r.returncode,flush=True)
 if args[0]=="systemctl":
  print(r.stdout[:5000],flush=True)
  m=re.search(r"MainPID=(\d+)",r.stdout)
  if m and m.group(1)!="0":
   try:
    raw=open("/proc/"+m.group(1)+"/environ","rb").read().split(b"\0")
    keys=sorted(x.split(b"=",1)[0].decode("ascii","ignore") for x in raw if b"=" in x)
    print("PROCESS_ENV_KEY_NAMES",[k for k in keys if any(t in k.upper() for t in ("KIWOOM","APP_KEY","APP_SECRET","TOKEN","ACCOUNT","CLIENT"))],flush=True)
   except Exception as e: print("PROC_ENV_READ",type(e).__name__,flush=True)
 else:
  lines=[x for x in r.stdout.splitlines() if any(t in x.upper() for t in ("ETF","KIWOOMREADONLYERROR","KIWOOM_","QUOTE"))]
  print("RELEVANT_LOGS\n"+"\n".join(lines[-100:]),flush=True)
