"""Read-only deployment audit. Never queries or writes Neon, never calls Groq."""
import hashlib, pathlib, importlib.util, json, sys
app=pathlib.Path("/opt/gaemigtp-news/app")
p=app/"backend/services/us_market_close.py"
b=p.read_bytes()
expected="2092adbdfdf60b432d6ac4b09aeb01c0f85ef249"
import subprocess
actual=subprocess.check_output(["git","hash-object",str(p)],text=True).strip()
print("US_CLOSE_DEPLOY_BLOB_SHA="+actual,flush=True)
print("US_CLOSE_DEPLOY_MATCH="+str(actual==expected),flush=True)
t=b.decode("utf-8")
print("NEW_SUMMARY_EXAMPLE="+str('"summary":"쉽고 구체적인 내용"' in t),flush=True)
print("OLD_SUMMARY_EXAMPLE="+str('"summary":"기사에 근거한 내용"' in t),flush=True)
for fn in ("backend/services/us_market_close_runtime.py","backend/us_market_close_job.py"):
 print("OTHER_RUNTIME_EXISTS_"+fn+"="+str((app/fn).exists()),flush=True)
if actual!=expected: raise SystemExit("MISMATCH_DEPLOYED_SOURCE")
