#!/usr/bin/env python3
"""Read-only inventory of accessible DigitalOcean application and temporary files."""
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

def walk(root, max_items=700, max_depth=5):
    base=Path(root)
    try:
        st=base.lstat()
    except FileNotFoundError:
        return {"root":root,"exists":False,"items":[],"count":0}
    except Exception as e:
        return {"root":root,"accessible":False,"error":type(e).__name__,"items":[]}
    if stat.S_ISLNK(st.st_mode):
        return {"root":root,"accessible":False,"error":"symlink_root","items":[]}
    out=[]
    for cur,dirs,files in os.walk(base,topdown=True,followlinks=False):
        rel=Path(cur).relative_to(base)
        depth=len(rel.parts)
        dirs[:]=[d for d in dirs if not (Path(cur)/d).is_symlink()]
        if depth>=max_depth: dirs[:]=[]
        for n in dirs+files:
            p=Path(cur)/n
            rec=item(p)
            out.append(rec)
            if len(out)>=max_items: break
        if len(out)>=max_items: break
    return {"root":root,"accessible":True,"count_listed":len(out),"truncated":len(out)>=max_items,"items":out}

roots=[
 "/opt/gaemigtp-news/app/ops",
 "/opt/gaemigtp-news/app/backend",
 "/run/gaemi-gateway",
 "/tmp",
 "/var/tmp",
 "/var/lib/gaemigtp-news",
]
result={"mode":"READ_ONLY","roots":[walk(p) for p in roots]}
print(json.dumps(result,ensure_ascii=False,separators=(",",":")))
