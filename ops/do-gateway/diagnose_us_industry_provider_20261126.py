"""Read-only diagnosis of live Kiwoom US industry provider and serving process."""
import json
import os
import pathlib
import subprocess
import sys
import time

APP = pathlib.Path("/opt/gaemigtp-news/app")
sys.path.insert(0, str(APP))

def safe_cmd(args):
    p = subprocess.run(args, text=True, capture_output=True, timeout=10)
    return (p.stdout or "").strip()

def main():
    print("DIAG_START=1", flush=True)
    for unit in ("gaemigtp-kiwoom-us-top20-api.service", "gaemigtp-kiwoom-us-top20-https.service"):
        print("UNIT_" + unit + "_ACTIVE=" + safe_cmd(["systemctl", "is-active", unit]), flush=True)
        props = safe_cmd(["systemctl", "show", unit, "-p", "MainPID", "-p", "ExecStart", "-p", "WorkingDirectory", "-p", "EnvironmentFiles"])
        print("UNIT_" + unit + "_PROPS=" + json.dumps(props), flush=True)

    pid_text = safe_cmd(["systemctl", "show", "gaemigtp-kiwoom-us-top20-api.service", "-p", "MainPID", "--value"])
    try:
        pid = int(pid_text)
    except Exception:
        pid = 0
    print("API_PID=" + str(pid), flush=True)
    if pid > 1:
        try:
            print("API_CMDLINE=" + pathlib.Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\\0", b" ").decode("utf-8", "replace")[:500], flush=True)
            print("API_CWD=" + str(pathlib.Path(f"/proc/{pid}/cwd").resolve()), flush=True)
            raw_env = pathlib.Path(f"/proc/{pid}/environ").read_bytes().split(b"\\0")
            for item in raw_env:
                if item.startswith((b"GAEMI_KIWOOM_APP_KEY=", b"GAEMI_KIWOOM_APP_SECRET=")):
                    k, v = item.split(b"=", 1)
                    os.environ[k.decode()] = v.decode()
        except Exception as exc:
            print("API_PROC_INSPECT_ERROR=" + type(exc).__name__, flush=True)

    try:
        from backend.providers import kiwoom_us_industries as provider
        from backend.providers.kiwoom_us_quotes import KiwoomReadOnlyError
        token = provider._access_token()
        official_data = provider._call("usa10101", {"gubun": "1"}, token=token)
        perf_data = provider._call("usa23000", {"stex_tp": "0", "inds_cd": "0"}, token=token)
        official = official_data.get("list")
        performance = perf_data.get("result_list")
        def describe(rows):
            if not isinstance(rows, list):
                return {"is_list": False, "type": type(rows).__name__}
            sample = next((r for r in rows if isinstance(r, dict)), {})
            return {
                "is_list": True, "count": len(rows),
                "sample_keys": sorted(str(k) for k in sample.keys())[:80],
                "sample_inds_cd": sample.get("inds_cd"),
                "sample_perf_1d": sample.get("perf_1d"),
                "sample_perf_5d": sample.get("perf_5d"),
            }
        print("USA10101=" + json.dumps(describe(official), ensure_ascii=False), flush=True)
        print("USA23000=" + json.dumps(describe(performance), ensure_ascii=False), flush=True)
        if isinstance(official, list) and isinstance(performance, list):
            built = provider._build_us_industry_map(official, performance, provider.INDUSTRY_GROUPS)
            print("BUILT_HEATMAP=" + json.dumps({
                "fetched_at": built.get("fetched_at"),
                "mapping_complete": built.get("mapping_complete"),
                "items": [{k: row.get(k) for k in ("key","change_pct","mapping_status","codes")} for row in built.get("items", [])]
            }, ensure_ascii=False, allow_nan=False), flush=True)
    except Exception as exc:
        message = str(exc)
        safe = message if len(message) <= 100 and all(c.isalnum() or c in "_-" for c in message) else type(exc).__name__
        print("PROVIDER_ERROR_CLASS=" + type(exc).__name__, flush=True)
        print("PROVIDER_ERROR_CODE=" + safe, flush=True)
    print("DIAG_END=1", flush=True)

if __name__ == "__main__":
    main()
