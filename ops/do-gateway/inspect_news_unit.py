from __future__ import annotations
import subprocess

cmd=["systemctl","cat","gaemigtp-news.service"]
p=subprocess.run(cmd,text=True,capture_output=True,check=False)
print("RETURN_CODE="+str(p.returncode))
print(p.stdout)
if p.stderr:
    print("STDERR="+p.stderr)
