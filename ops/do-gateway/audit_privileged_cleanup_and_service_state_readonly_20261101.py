#!/usr/bin/env python3
"""Read-only privilege, retention and failed-unit check."""
import subprocess,json,os
def r(a):
 try:
  p=subprocess.run(a,capture_output=True,text=True,timeout=25)
  return {"rc":p.returncode,"out":p.stdout[:6000],"err":p.stderr[:1000]}
 except Exception as e:return {"error":type(e).__name__+":"+str(e)[:200]}
print("IDENTITY",r(["id"]))
print("SUDO_ALLOWLIST",r(["sudo","-n","-l"]))
for u in ["gaemigtp-news.service","gaemigtp-kiwoom-us-daily.service","gaemigtp-kiwoom-us-value.service","gaemigtp-us-market-close.service","gaemigtp-us-market-close.timer"]:
 print("UNIT",u,r(["systemctl","show",u,"-p","LoadState","-p","ActiveState","-p","SubState","-p","Result","-p","ExecMainStatus","-p","ExecMainCode","-p","FragmentPath"]))
for p in ["/etc/systemd/journald.conf","/etc/logrotate.conf","/etc/logrotate.d/btmp","/var/cache/apt/archives","/var/log/journal","/var/log/btmp","/run/gaemi-gateway"]:
 print("STAT",p,r(["stat","-c","%F %U:%G %a %s %y %n",p]))
print("JOURNAL_RETENTION_CONFIG",r(["bash","-lc","grep -E '^[[:space:]]*(SystemMaxUse|SystemKeepFree|SystemMaxFileSize|MaxRetentionSec|RuntimeMaxUse|Storage)=' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*.conf 2>/dev/null || true"]))
print("LOGROTATE_BTMP_CONFIG",r(["bash","-lc","cat /etc/logrotate.d/btmp 2>/dev/null || true"]))
print("AUDIT_COMPLETE")
