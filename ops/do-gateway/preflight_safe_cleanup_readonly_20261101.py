#!/usr/bin/env python3
"""Read-only preflight for exact disposable artifacts; no changes."""
import subprocess, json
def run(a):
 p=subprocess.run(a,capture_output=True,text=True,timeout=40)
 print(json.dumps({"cmd":a,"rc":p.returncode,"out":p.stdout[:7000],"err":p.stderr[:1000]},ensure_ascii=False))
run(["find","/run/gaemi-gateway","-maxdepth","1","-type","f","-printf","%s %TY-%Tm-%TdT%TH:%TM %u:%g %m %p\\n"])
run(["grep","-R","-n","-F","nvda-news-test-20261028.json","/opt/gaemigtp-news/app"])
run(["bash","-lc","find /opt/gaemigtp-news/app -xdev -type f -name '*.pyc' -printf '%s %p\\n' | awk '{n++;s+=$1} END {print \"PYC_FILES\",n,\"BYTES\",s}'"])
run(["find","/opt/gaemigtp-news/app","-xdev","-type","f","\\(","-name","*.bak","-o","-name","*.old","-o","-name","*.next","\\)","-printf","%s %TY-%Tm-%Td %p\\n"])
run(["systemctl","--failed","--no-pager","--plain"])
print("PREFLIGHT_COMPLETE_NO_CHANGES")
