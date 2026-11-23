"""Read-only: the `logs` gateway op (run as root, journalctl -u ... -n 300)
showed ONLY systemd lifecycle lines (Started/Stopping/Deactivated/Consumed)
across a 300-line, ~2-week window -- not a single one of this app's own
print(...) lines (e.g. KIWOOM_QQQ_FE_THREAD_STARTED, which should fire on
every one of the ~17 startups seen in that window). That means either the
app's stdout isn't reaching the journal at all, or it's crashing before
that line ever runs -- either way, worth seeing the actual unit file
(usually world-readable) to check how output is routed."""
import pathlib

for path in (
    "/etc/systemd/system/gaemigtp-kiwoom-us-top20-api.service",
    "/etc/systemd/system/gaemigtp-kiwoom-us-top20-https.service",
):
    p = pathlib.Path(path)
    try:
        print("=== " + path + " ===", flush=True)
        print(p.read_text(), flush=True)
    except Exception as exc:
        print(path, "READ_ERROR", repr(exc), flush=True)
