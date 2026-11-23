"""Read-only: the gaemigtp-kiwoom-us-top20-api service has been restarting
unusually often (every few to few dozen minutes, visible even in a plain
`logs` pull). ETF websocket registration is the LAST step in that service's
startup sequence (QQQ -> TOP20 -> industry stocks -> ETF), so frequent
restarts could explain why ETF sector data is flaky while everything else
(stocks, QQQ) looks fine -- earlier groups finish fast, the ETF group is
the one most likely to get cut off. This pulls a much larger journal window
than the capped `logs` gateway op allows (max 300 total lines, mostly eaten
by restart noise) and filters it down server-side to just: the count/timing
of recent restarts, any crash/exception lines, and the ETF/TOP20/industry
FE registration result lines, so the actual pattern is visible instead of
drowned out."""
import subprocess

result = subprocess.run(
    ["journalctl", "--no-pager", "-u", "gaemigtp-kiwoom-us-top20-api.service",
     "--since", "6 hours ago"],
    capture_output=True, text=True, timeout=30,
)
print("RETURNCODE", result.returncode, flush=True)
print("STDERR", repr(result.stderr[:500]), flush=True)
lines = result.stdout.splitlines()
print("TOTAL_LINES_LAST_6H", len(lines), flush=True)
if lines:
    print("FIRST_LINE", lines[0][:160], flush=True)
    print("LAST_LINE", lines[-1][:160], flush=True)

starts = [l for l in lines if "Started gaemigtp-kiwoom-us-top20-api" in l]
stops = [l for l in lines if "Stopping gaemigtp-kiwoom-us-top20-api" in l]
print("RESTART_COUNT_LAST_6H", len(starts), flush=True)
print("LAST_10_START_STOP_TIMES", flush=True)
for l in (stops + starts)[-20:]:
    print("  ", l[:80], flush=True)

print("CONSUMED_LINES (why it stopped, if shown)", flush=True)
for l in lines:
    if "Consumed" in l or "code=" in l or "status=" in l or "Main process exited" in l:
        print("  ", l[:160], flush=True)

print("ETF_FE_REGISTRATION_LINES", flush=True)
for l in lines:
    if "KIWOOM_ETF_FE_REGISTERED" in l or "KIWOOM_ETF_FE_REGISTRATION_FAILED" in l \
       or "KIWOOM_TOP20_FE_REGISTERED" in l or "KIWOOM_INDUSTRY_STOCK_FE_REGISTERED" in l \
       or "KIWOOM_QQQ_FE_THREAD_STARTED" in l or "KIWOOM_MARKET_WIDGET_FE_REGISTRATION_FAILED" in l:
        print("  ", l[:160], flush=True)

print("TRACEBACK_OR_ERROR_LINES (sample)", flush=True)
shown = 0
for l in lines:
    if ("Traceback" in l or "Error" in l or "error" in l.lower()) and shown < 40:
        print("  ", l[:160], flush=True)
        shown += 1
