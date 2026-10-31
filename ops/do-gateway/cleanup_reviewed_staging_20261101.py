"""Delete only reviewed stale staging artifacts; preserve every rollback backup."""
from pathlib import Path
import hashlib, time, json, subprocess, sys

APP=Path("/opt/gaemigtp-news/app")
OPS=APP/"ops"
AUDIT_NAME="audit_server_staging_refs_20261101.py"
CLEANUP_NAME="cleanup_reviewed_staging_20261101.py"
EXPECTED={
"staged_daily_issue_schedule.py":"f7ab637f217d864bd9ffed59d168eff962b4d358411a6f9a3818b1f34ed187bd",
"staged_news_processed_store.py":"1681815be7359bbce0d905efc0c3db50315ae93cb616051320fee887dde94cdb",
".us-code-next-result.py":"95a1c3ad9f47fb86cee9a1997219490a5c391c228a34d5f5461bbc7df37f37dd",
"staged_ai_issue_display_adapter.py":"fb6bd641025239bd771103a5fa3227fab52976088da9da51d777384bcd787f62",
".next-shared-news-result.py":"6436c852a8d12578c046eb6c45fbb08d2fc55f9b09710127396a5ea54554f953",
".next-shared-source-meta.py":"a7bed667d6fe105abe92293ee9b94ad4048a7d46b008dfaef144cb2ea765d1bc",
".news-coverage-rank-patch.next":"e7ee06e85b83fe500583f92b6a774aa18e9639355e51f35626d8f7de86b28212",
".next-shared-news-feed.py":"a4544237a20b45cc02ddf9a320741acd6a5c2c04c6a9db20e503442a5834c7a0",
".identity-resolver.next":"b7c6d733eff2affa9cb4088b88b4522ec74afd62be1111391445c3c06745dff8",
".news-coverage-catalog.next":"ef8200ce8513e972009e71f6440f67a25dcf6dfb68db8c0dbd989fd3993cc75c",
".us-code-next-store.py":"808f110c408260b0adf1f564741820d8f43705a7c6ccba4745fccfbd8b5f018d",
".us-identity-next-news.py":"0f79aeb99a5931f22273ce4250c8cc3c9eca08734811add49c5ffd7a798f7a58",
"staged_news_rank_queue_patch.py":"e7ee06e85b83fe500583f92b6a774aa18e9639355e51f35626d8f7de86b28212",
".us-identity-next-store.py":"24b488568a5354c7fd7c8dab50cd28c880022bc06e8f2ad2893508e52fc8a156",
".identity-catalog.next":"27eca973c92c98fbee0b13d3c448fd705a1c371fb73bf0f8fec2ec656eea428e",
"staged_daily_call_guard.py":"aaa04a963104ec275338428a2ec699cd2e3fe682b181b6032125374aa8494d6b",
".us-code-next-citations.py":"2aada3aad3f18ad1d42e383efadd3c08c39e4cfae3c6bdcc819d43b985120d1a",
".next-shared-processed-store.py":"ca27f46367a8751b316af773a6663173501736a9d366665db9e93665a54b352e",
"staged_ai_snapshot_integration.py":"1677d26584377132ffdb51eaf2eaa8590498079042c54a78535b3f666d79dae3",
}
def require_inactive():
    active=subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True).stdout.strip()
    if active=="active": raise SystemExit("ABORT: news worker is active")
require_inactive()
roots=[APP/"backend",APP/"frontend",APP/"app.py",OPS,Path("/etc/systemd/system"),Path("/etc/cron.d"),Path("/etc/cron.daily"),Path("/etc/cron.hourly")]
checked=[]
for name,expected in EXPECTED.items():
    p=OPS/name
    if not p.exists() and not p.is_symlink():
        raise SystemExit("ABORT: candidate missing: "+name)
    if p.is_symlink() or not p.is_file():
        raise SystemExit("ABORT: unexpected candidate type: "+name)
    st=p.stat()
    if time.time()-st.st_mtime < 7*86400:
        raise SystemExit("ABORT: candidate younger than 7 days: "+name)
    actual=hashlib.sha256(p.read_bytes()).hexdigest()
    if actual!=expected:
        raise SystemExit("ABORT: content hash changed: "+name)
    refs=[]
    for root in roots:
        if not root.exists(): continue
        files=[root] if root.is_file() else root.rglob("*")
        for f in files:
            try:
                if not f.is_file() or f.is_symlink() or f==p: continue
                if f.name in (AUDIT_NAME,CLEANUP_NAME): continue
                if f.stat().st_size>2_000_000: continue
                if name.encode() in f.read_bytes(): refs.append(str(f))
            except (OSError,PermissionError):
                pass
    if refs:
        raise SystemExit("ABORT: candidate now referenced: "+name+" by "+json.dumps(sorted(set(refs))))
    checked.append((p,st.st_size,actual))
# Backups, restore scripts, credentials, runtime files and recent staging artifacts are outside this exact allowlist.
for p,size,digest in checked:
    p.unlink()
    if p.exists() or p.is_symlink(): raise SystemExit("DELETE_VERIFY_FAILED: "+str(p))
require_inactive()
print("DELETED_COUNT",len(checked),flush=True)
print("DELETED_BYTES",sum(x[1] for x in checked),flush=True)
for p,size,digest in checked:
    print("DELETED",str(p),"bytes="+str(size),"sha256="+digest,flush=True)
print("PRESERVED rollback backups, restore helpers, .groq_api_key, news-worker scripts, gateway allowlisted staged_daily_groq_issues.py, and all files with live/helper references.",flush=True)
print("NEWS_WORKER_REMAINS_INACTIVE",flush=True)
print("REVIEWED_STAGING_CLEANUP_DONE",flush=True)
