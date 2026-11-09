"""Read-only inspect of deployed TOP20→R2 call graph and R2 key collision."""
from __future__ import annotations
import ast,hashlib
from pathlib import Path
import subprocess
root=Path("/opt/gaemigtp-news/app")
files={"top20":"backend/news_worker.py","store":"backend/services/news_processed_store.py","uploader":"backend/services/r2_news_uploader.py","tradingview":"backend/tradingview_news_worker.py"}
print("TOP20_R2_AUDIT_BEGIN=1")
for name,rel in files.items():
    path=root/rel
    safe=path.is_file() and not path.is_symlink()
    print(name.upper()+"_FILE_PRESENT="+str(safe))
    if not safe:continue
    data=path.read_bytes()
    print(name.upper()+"_SHA256="+hashlib.sha256(data).hexdigest())
    try: tree=ast.parse(data,filename=str(path))
    except SyntaxError:
        print(name.upper()+"_SYNTAX_VALID=False");continue
    print(name.upper()+"_SYNTAX_VALID=True")
    imports=[]
    calls=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom):
            imports.append((node.module or "",[i.name for i in node.names]))
        elif isinstance(node,ast.Call):
            fn=node.func
            if isinstance(fn,ast.Name):calls.append(fn.id)
            elif isinstance(fn,ast.Attribute):calls.append(fn.attr)
    print(name.upper()+"_IMPORTS_R2="+str(any("r2" in module.lower() or any("r2" in x.lower() or "upload" in x.lower() for x in names) for module,names in imports)))
    print(name.upper()+"_CALLS_UPLOAD_FILE="+str("upload_file" in calls))
    print(name.upper()+"_CALLS_SAVE_SNAPSHOT="+str("save_snapshot" in calls))
    if name=="uploader":
        keys=[node.value.value for node in ast.walk(tree)
              if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="OBJECT_KEY" for t in node.targets)
              and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)]
        print("UPLOADER_OBJECT_KEY="+(keys[0] if keys else "unknown"))
for unit in ("gaemigtp-news.service","gaemigtp-tradingview-news.service"):
    p=subprocess.run(["systemctl","show",unit,"--property=ActiveState,UnitFileState","--no-pager"],capture_output=True,text=True,timeout=8)
    for line in p.stdout.splitlines():
        print("UNIT_"+unit.replace(".","_")+"_"+line)
print("TOP20_R2_AUDIT_END=1")
