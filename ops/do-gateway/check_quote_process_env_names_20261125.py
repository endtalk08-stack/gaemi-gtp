import os
for pid in ("745106","748351"):
 try:
  raw=open("/proc/"+pid+"/environ","rb").read().split(b"\0")
  keys=sorted(x.split(b"=",1)[0].decode("ascii","ignore") for x in raw if b"=" in x)
  print("PID",pid,"KEYS",[k for k in keys if any(x in k.upper() for x in ("KIWOOM","APP","KEY","SECRET","TOKEN"))],flush=True)
  print("UID",open("/proc/"+pid+"/status").read().split("Uid:",1)[1].splitlines()[0].strip(),flush=True)
 except Exception as e: print("PID_ERROR",pid,type(e).__name__,flush=True)
