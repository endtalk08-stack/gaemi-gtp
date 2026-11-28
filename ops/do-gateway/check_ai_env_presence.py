#!/usr/bin/env python3
"""Read-only check for three AI-test environment keys. Never print values."""
from pathlib import Path
import re
import sys

TARGETS = ("AI_TEST_TOKEN", "AI_TEST_ENABLED", "GROQ_API_KEY")
ENV_FILES = (
    Path("/etc/gaemigtp/news-worker.env"),
    Path("/var/lib/gaemigtp-news/r2.env"),
)
ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")

def nonempty_assignment(raw):
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return bool(value.strip())

def main():
    found = set()
    for path in ENV_FILES:
        try:
            if path.is_symlink() or not path.is_file():
                continue
            # Read only the approved env files; never echo their contents.
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip() or line.lstrip().startswith("#"):
                        continue
                    match = ASSIGNMENT.match(line.rstrip("\r\n"))
                    if match and match.group(1) in TARGETS and nonempty_assignment(match.group(2)):
                        found.add(match.group(1))
        except (OSError, UnicodeError):
            # Unreadable files do not count as configured.
            continue

    for key in TARGETS:
        print(f"{key}: {'설정됨' if key in found else '누락'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
