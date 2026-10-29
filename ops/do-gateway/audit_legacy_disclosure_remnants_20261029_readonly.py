"""Read-only legacy disclosure file and reference audit. No provider or DB access."""
from pathlib import Path
import hashlib
import os
import subprocess

APP = Path("/opt/gaemigtp-news/app")
NAMES = ("disclosure_single_collect.py", "disclosure_universe.py")
TARGETS = tuple(APP / "backend/services" / name for name in NAMES)
STAGE = Path("/home/gaemi-deploy/disclosures-migration-staging/user40-ready")

print("LEGACY_DISCLOSURE_READONLY_AUDIT_BEGIN", flush=True)
print("ACCOUNT=" + str(os.geteuid()), flush=True)
for path in (*TARGETS, *(STAGE / name for name in NAMES)):
    try:
        if not path.exists():
            print("FILE_STATE=" + str(path) + ":absent", flush=True)
        elif path.is_symlink() or not path.is_file():
            print("FILE_STATE=" + str(path) + ":unexpected_file_type", flush=True)
        else:
            meta = path.stat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            print("FILE_STATE=" + str(path) + ":present:sha256=" + digest +
                  ":owner_uid=" + str(meta.st_uid) + ":mode=" + oct(meta.st_mode & 0o777), flush=True)
    except PermissionError:
        print("FILE_STATE=" + str(path) + ":permission_denied", flush=True)

tokens = ("disclosure_single_collect", "disclosure_universe")
extensions = {".py", ".sh", ".service", ".timer", ".yml", ".yaml"}
exclude = set(TARGETS)
checked = 0
hits = []
for root in (APP / "backend", APP / "ops"):
    if not root.exists():
        continue
    for directory, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".venv", "venv", "node_modules"}]
        for name in names:
            p = Path(directory) / name
            if p in exclude or p.suffix not in extensions or p.is_symlink():
                continue
            try:
                if p.stat().st_size > 1024 * 1024:
                    continue
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                checked += 1
                for index, line in enumerate(lines, 1):
                    if any(token in line for token in tokens):
                        hits.append(str(p.relative_to(APP)) + ":" + str(index))
            except (PermissionError, OSError):
                print("SKIPPED_UNREADABLE=" + str(p.relative_to(APP)), flush=True)
unit_root = Path("/etc/systemd/system")
if unit_root.is_dir():
    for p in unit_root.glob("gaemigtp-*"):
        if p.suffix not in {".service", ".timer"} or not p.is_file():
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            checked += 1
            for index, line in enumerate(lines, 1):
                if any(token in line for token in tokens):
                    hits.append(str(p) + ":" + str(index))
        except (PermissionError, OSError):
            print("SKIPPED_UNREADABLE=" + str(p), flush=True)
print("REFERENCE_FILES_CHECKED=" + str(checked), flush=True)
for hit in hits[:100]:
    print("REFERENCE_FOUND=" + hit, flush=True)
print("REFERENCE_MATCHES=" + str(len(hits)), flush=True)
check = subprocess.run(["systemctl", "list-timers", "--all", "--no-pager", "--no-legend"],
                       capture_output=True, text=True, timeout=12, check=False)
print("TIMERS_COMMAND_EXIT=" + str(check.returncode), flush=True)
for line in check.stdout.splitlines():
    if any(word in line.lower() for word in ("disclos", "dart", "sec-filings")):
        print("DISCLOSURE_TIMER=" + line.strip()[:250], flush=True)
print("LEGACY_DISCLOSURE_READONLY_AUDIT_END", flush=True)
