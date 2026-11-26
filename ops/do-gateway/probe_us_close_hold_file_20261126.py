"""Read-only probe of the held last-regular-close file and unit write sandbox.

Prints only dates, symbol names, counts and systemd sandbox properties.
"""
import json
import pathlib
import subprocess

FILE = pathlib.Path("/var/lib/gaemigtp-news/us-regular-last-verified.json")
ETFS = ("XLK", "XLV", "XLF", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB", "SOXX", "XBI", "IBIT")


def main():
    try:
        st = FILE.stat()
        print("HOLD_FILE_EXISTS=1 size=%d mtime=%d" % (st.st_size, int(st.st_mtime)), flush=True)
        data = json.loads(FILE.read_text(encoding="utf-8"))
        items = data.get("items") or {}
        print("HOLD_FILE_DAY=%s symbols=%d" % (data.get("day"), len(items)), flush=True)
        print("HOLD_FILE_ETFS_PRESENT=" + ",".join(s for s in ETFS if s in items), flush=True)
    except FileNotFoundError:
        print("HOLD_FILE_EXISTS=0", flush=True)
    except Exception as exc:
        print("HOLD_FILE_READ_ERROR=" + type(exc).__name__, flush=True)
    try:
        d = FILE.parent.stat()
        print("HOLD_DIR_MODE=%o uid=%d gid=%d" % (d.st_mode & 0o7777, d.st_uid, d.st_gid), flush=True)
    except Exception as exc:
        print("HOLD_DIR_ERROR=" + type(exc).__name__, flush=True)
    for unit in ("gaemigtp-kiwoom-us-top20-api.service", "gaemigtp-kiwoom-us-top20-https.service"):
        out = subprocess.run(["systemctl", "show", unit, "-p", "ProtectSystem", "-p", "ReadWritePaths",
                              "-p", "StateDirectory", "-p", "ActiveEnterTimestamp"],
                             text=True, capture_output=True).stdout
        print("UNIT %s %s" % (unit, json.dumps(out.strip())), flush=True)


if __name__ == "__main__":
    main()
