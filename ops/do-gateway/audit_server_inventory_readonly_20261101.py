#!/usr/bin/env python3
"""Read-only inventory of files actually persisted on the DigitalOcean host."""
import os, stat, json, time
from pathlib import Path

def item(p):
    try:
        s=p.lstat()
        return {
            "path":str(p),"type":"symlink" if stat.S_ISLNK(s.st_mode) else ("dir" if stat.S_ISDIR(s.st_mode) else "file"),
            "bytes":s.st_size,"mtime":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(s.st_mtime)),
            "age_days":round((time.time()-s.st_mtime)/86400,1),
            "owner_uid":s.st_uid,"group_gid":s.st_gid,"mode":oct(stat.S_IMODE(s.st_mode))
        }
    except Exception as e:return {"path":str(p),"error":type(e).__name__}

def walk(root, max_items=400, max_depth=4):
    base=Path(root)
    if not base.exists():
        return {"root":root,"exists":False,"items":[],"count":0}
    out=[]
    for cur,dirs,files in os.walk(base,topdown=True,followlinks=False):
        rel=Path(cur).relative_to(base)
        depth=len(rel.parts)
        dirs[:]=[d for d in dirs if not (Path(cur)/d).is_symlink()]
        if depth>=max_depth: dirs[:]=[]
        for n in dirs+files:
            p=Path(cur)/n
            if p.is_symlink():
                out.append(item(p)); continue
            if p.is_file() or p.is_dir():
                out.append(item(p))
            if len(out)>=max_items: break
        if len(out)>=max_items: break
    return {"root":root,"exists":True,"count_listed":len(out),"truncated":len(out)>=max_items,"items":out}

roots=[
 "/opt/gaemigtp-news/app/ops",
 "/opt/gaemigtp-news/app/backend",
 "/home/gaemi-deploy/.gaemi-gateway",
 "/run/gaemi-gateway",
 "/var/lib/gaemi-gateway",
 "/var/lib/gaemigtp-news",
 "/tmp",
 "/var/tmp",
]
result={"mode":"READ_ONLY","roots":[walk(p) for p in roots]}
print(json.dumps(result,ensure_ascii=False,separators=(",",":")))
