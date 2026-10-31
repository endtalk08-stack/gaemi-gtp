#!/usr/bin/env python3
"""Read-only inventory of persistent gateway payloads and temporary files."""
import os, subprocess, json
def run(label, cmd, timeout=35):
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        print("## "+label+" rc="+str(p.returncode))
        print((p.stdout or "")[:12000])
        if p.stderr: print("STDERR",p.stderr[:1200])
    except Exception as e: print("## "+label+" ERROR "+type(e).__name__+":"+str(e)[:250])
print("IDENTITY")
run("id",["id"])
run("df",["df","-hT"])
for root in [
 "/home/gaemi-deploy/.gaemi-gateway",
 "/home/gaemi-deploy",
 "/run/gaemi-gateway",
 "/tmp",
 "/var/tmp",
 "/var/lib/gaemigtp-news",
 "/opt/gaemigtp-news/app",
 "/var/cache",
 "/var/log",
]:
    run("DU "+root,["du","-x","-h","-d","2",root],40)
    run("FILES "+root,["bash","-lc","if test -d "+root+"; then find "+root+" -xdev -maxdepth 4 -type f -printf '%s|%TY-%Tm-%TdT%TH:%TM:%TS|%u:%g|%m|%p\\n' 2>/dev/null | sort -nr | head -120; else echo MISSING; fi"],40)
run("APP_TEMP_CANDIDATES",["bash","-lc","find /opt/gaemigtp-news/app -xdev -type f \\( -name '*.pyc' -o -name '*.pyo' -o -name '*.tmp' -o -name '*.bak' -o -name '*.old' -o -name '*~' -o -name 'test_*.py' -o -name 'audit_*_readonly*.py' \\) -printf '%s|%TY-%Tm-%TdT%TH:%TM:%TS|%u:%g|%p\\n' 2>/dev/null | sort -nr | head -250"],40)
run("HOME_TOP_LEVEL",["bash","-lc","find /home/gaemi-deploy -mindepth 1 -maxdepth 1 ! -name '.ssh' -printf '%y|%s|%TY-%Tm-%Td|%p\\n' 2>/dev/null"])
print("PERSISTED_WORKFILES_AUDIT_COMPLETE")
