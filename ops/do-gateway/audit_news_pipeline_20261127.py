"""Read-only audit of the news pipeline: units, timers, recent logs, files, env key names."""
import json
import os
import pathlib
import subprocess


def sh(cmd):
    return subprocess.run(cmd, text=True, capture_output=True).stdout.strip()


def main():
    units = sh(["systemctl", "list-unit-files", "gaemigtp-*", "--no-legend", "--no-pager"])
    print("UNIT_FILES\n" + units, flush=True)
    print("ACTIVE\n" + sh(["systemctl", "list-units", "gaemigtp-*", "--all", "--no-legend", "--no-pager"]), flush=True)
    print("TIMERS\n" + sh(["systemctl", "list-timers", "gaemigtp-*", "--all", "--no-legend", "--no-pager"]), flush=True)
    for unit in [line.split()[0] for line in units.splitlines() if "news" in line.split()[0] or "close" in line.split()[0]]:
        if not unit.endswith(".service"):
            continue
        props = sh(["systemctl", "show", unit, "-p", "ExecStart", "-p", "EnvironmentFiles", "-p", "ActiveState",
                    "-p", "UnitFileState", "-p", "ExecMainExitTimestamp"])
        print("UNIT " + unit + " " + json.dumps(props), flush=True)
        log = sh(["journalctl", "-u", unit, "-n", "12", "--no-pager", "-o", "short-iso"])
        print("LOG " + unit + "\n" + "\n".join(l[:220] for l in log.splitlines()), flush=True)
    print("JOB_ENV_KEYS " + ",".join(sorted(k for k in os.environ if any(t in k for t in ("NAVER", "GROQ", "R2", "NEWS", "DATABASE", "CLOUDFLARE", "AWS")))), flush=True)
    data = pathlib.Path("/var/lib/gaemigtp-news")
    try:
        for p in sorted(data.iterdir()):
            st = p.stat()
            print("DATA %s %d %d" % (p.name, st.st_size, int(st.st_mtime)), flush=True)
    except Exception as exc:
        print("DATA_ERROR " + type(exc).__name__, flush=True)
    app = pathlib.Path("/opt/gaemigtp-news/app/backend")
    for name in ("news_worker.py", "services/r2_news_uploader.py", "services/news_r2_ai.py", "services/news_feed.py", "providers/naver_news.py", "services/news_detail.py", "services/verified_fact_headline.py"):
        p = app / name
        print("FILE %s exists=%s size=%s" % (name, p.exists(), p.stat().st_size if p.exists() else 0), flush=True)


if __name__ == "__main__":
    main()
