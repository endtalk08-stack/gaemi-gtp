#!/usr/bin/env python3
"""Read-only DigitalOcean storage/cache/service inventory. Never deletes or edits."""
import json, os, shutil, subprocess
from pathlib import Path

def run(args, timeout=25):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
        out=(p.stdout or "").strip()
        err=(p.stderr or "").strip()
        if p.returncode:
            return {"rc":p.returncode,"out":out[:5000],"err":err[:1200]}
        return {"rc":0,"out":out[:9000]}
    except Exception as e:
        return {"error":type(e).__name__+":"+str(e)[:250]}

def section(name, args, timeout=25):
    print("## "+name)
    print(json.dumps(run(args,timeout),ensure_ascii=False))

print("AUDIT_MODE=READ_ONLY")
print("HOST",run(["hostnamectl","--static"]))
print("WHOAMI",run(["id"]))
section("FILESYSTEMS",["df","-hT"])
section("JOURNAL_SIZE",["journalctl","--disk-usage"])
section("SYSTEMD_TIMERS",["systemctl","list-timers","--all","--no-pager"])
section("GAEMIGTP_UNITS",["systemctl","list-units","--all","--no-pager","--plain","--no-legend","gaemigtp*"])
section("TOP_PROCESSES",["ps","-eo","pid,comm,etime,%mem,%cpu","--sort=-%mem"])
section("DOCKER_DISK",["docker","system","df"])
roots=[
 "/var/lib/gaemigtp-news","/var/cache","/var/log","/tmp","/var/tmp",
 "/opt/gaemigtp-news","/run"
]
for root in roots:
    p=Path(root)
    print("## PATH",root)
    try:
        st=p.lstat()
        print("EXISTS type=%s mode=%s owner_uid=%s group_gid=%s"%(("dir" if p.is_dir() else "file"),oct(st.st_mode&0o777),st.st_uid,st.st_gid))
    except Exception as e:
        print("STAT_ERROR",type(e).__name__,str(e)[:200])
        continue
    section("DU "+root,["du","-x","-h","-d","2",root],40)
    section("LARGEST_FILES "+root,["bash","-lc","find "+root+" -xdev -maxdepth 5 -type f -printf '%s %TY-%Tm-%TdT%TH:%TM %p\\n' 2>/dev/null | sort -nr | head -40"],40)
    section("CACHE_BACKUP_NAMES "+root,["bash","-lc","find "+root+" -xdev -maxdepth 5 \\( -iname '*cache*' -o -iname '*.bak' -o -iname '*.old' -o -iname '*.tmp' -o -iname '*backup*' \\) -printf '%y %s %p\\n' 2>/dev/null | head -100"],40)
print("## APP_TOP_LEVEL")
section("APP_TOP_LEVEL",["find","/opt/gaemigtp-news/app","-maxdepth","2","-mindepth","1","-printf","%y %s %TY-%Tm-%Td %p"])
print("## STORAGE_AUDIT_COMPLETE")
