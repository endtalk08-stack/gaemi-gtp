"""Rollback cleanup, targeted to two experimental domestic title modules only."""
import pathlib,sys,ast,os,json,hashlib,importlib
root=pathlib.Path("/opt/gaemigtp-news/app/backend/services")
for name in ("compact_issue_titles.py","shared_v1_issue_titles.py"):
 p=root/name
 if p.exists():
  p.unlink()
  print("REMOVED_EXPERIMENT_MODULE="+name,flush=True)
 else: print("EXPERIMENT_MODULE_ALREADY_ABSENT="+name,flush=True)
 for cache in (root/"__pycache__").glob(name[:-3]+".*.pyc"):
  cache.unlink()
  print("REMOVED_CACHE="+cache.name,flush=True)
for name in ("issue_briefs.py","news_result.py"):
 p=root/name
 source=p.read_text()
 ast.parse(source)
 print("ACTIVE_MODULE="+json.dumps({"file":name,"shared_v1_ref":"shared_v1_issue_titles" in source,"compact_ref":"compact_issue_titles" in source,"domestic_bypass":'if market not in ("국내", "kr")' in source},ensure_ascii=False),flush=True)
 assert "shared_v1_issue_titles" not in source and "compact_issue_titles" not in source
assert not (root/"compact_issue_titles.py").exists()
assert not (root/"shared_v1_issue_titles.py").exists()
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.issue_briefs import build_issue_briefs
from backend.services.news_result import _sanitize_news_display_briefs
print("BACKEND_IMPORTS_OK",flush=True)
print("ROLLBACK_CLEANUP_PASS",flush=True)
