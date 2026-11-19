"""Sample existing quote-origin and Droplet counters without generating quote traffic."""
import datetime as dt
import glob
import json
import os
import shutil
import statistics
import subprocess
import time
from pathlib import Path

UNIT = "gaemigtp-kiwoom-us-top20-https.service"
MIB = 1024 ** 2
UTC = dt.timezone.utc

def command(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=4)
        return result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""

def int_property(props, key):
    raw = props.get(key, "")
    if not raw.isdigit():
        return None
    value = int(raw)
    return value if value < 2**64 - 1 else None

def rss_bytes(pid):
    if not pid:
        return None
    try:
        lines = Path(f"/proc/{pid}/status").read_text().splitlines()
        return next(int(line.split()[1]) * 1024 for line in lines
                    if line.startswith("VmRSS:"))
    except (OSError, StopIteration, ValueError):
        return None

def sample():
    now = time.monotonic()
    cpu = [int(value) for value in Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
    memory = {line.split(":")[0]: int(line.split()[1]) * 1024
              for line in Path("/proc/meminfo").read_text().splitlines()
              if line.startswith(("MemTotal:", "MemAvailable:", "SwapTotal:", "SwapFree:"))}
    interface = {}
    for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        name, fields = line.split(":", 1)
        fields = fields.split()
        if name.strip() != "lo":
            interface[name.strip()] = (int(fields[0]), int(fields[8]))
    service_text = command("systemctl", "show", UNIT, "-p",
                           "MainPID,CPUUsageNSec,MemoryCurrent,IPIngressBytes,IPEgressBytes")
    props = dict(line.split("=", 1) for line in service_text.splitlines() if "=" in line)
    pid = int_property(props, "MainPID")
    return {
        "at": now, "total": sum(cpu), "idle": cpu[3] + cpu[4],
        "mem_total": memory["MemTotal"], "mem_available": memory["MemAvailable"],
        "swap_used": memory["SwapTotal"] - memory["SwapFree"], "net": interface,
        "service_pid": pid, "service_cpu": int_property(props, "CPUUsageNSec"),
        "service_mem": int_property(props, "MemoryCurrent"), "service_rss": rss_bytes(pid),
        "service_rx": int_property(props, "IPIngressBytes"),
        "service_tx": int_property(props, "IPEgressBytes"),
    }

def percent(previous, current):
    elapsed = current["total"] - previous["total"]
    return 100 * (1 - (current["idle"] - previous["idle"]) / elapsed) if elapsed > 0 else None

def rate(old, new, seconds):
    return (new - old) / seconds if old is not None and new is not None and new >= old else None

def avg_mib(values):
    values = [value for value in values if value is not None]
    return round(statistics.mean(values) / MIB, 2) if values else None

def peak_mib(values):
    values = [value for value in values if value is not None]
    return round(max(values) / MIB, 2) if values else None

def connections():
    output = command("ss", "-Htn", "state", "established", "( sport = :443 )")
    return len(output.splitlines()) if shutil.which("ss") else None

def historical():
    paths = [path for path in glob.glob("/var/log/sysstat/sa*") + glob.glob("/var/log/sa/sa*")
             if Path(path).name in ("sa19", "sa20", "sa20261119", "sa20261120")]
    sadf = shutil.which("sadf")
    if not sadf or not paths:
        return {"available": False, "sysstat_utility": bool(sadf), "sysstat_archives": len(paths)}
    windows = {
        "before": (dt.datetime(2026, 11, 19, 14, 55, tzinfo=UTC), dt.datetime(2026, 11, 19, 15, 5, tzinfo=UTC)),
        "after": (dt.datetime(2026, 11, 19, 15, 18, tzinfo=UTC), dt.datetime(2026, 11, 19, 15, 28, tzinfo=UTC)),
    }
    result = {label: [] for label in windows}
    for path in paths:
        raw = command(sadf, "-j", path, "--", "-u", "-r", "-n", "DEV")
        if not raw:
            continue
        try:
            hosts = json.loads(raw)["sysstat"]["hosts"]
        except (ValueError, KeyError, TypeError):
            continue
        for host in hosts:
            for row in host.get("statistics", []):
                stamp = row.get("timestamp", {})
                if stamp.get("utc") not in (1, True):
                    continue
                try:
                    at = dt.datetime.fromisoformat(stamp["date"] + "T" + stamp["time"]).replace(tzinfo=UTC)
                except (KeyError, ValueError):
                    continue
                for label, (start, end) in windows.items():
                    if start <= at < end:
                        all_cpu = next((item for item in row.get("cpu-load", []) if item.get("cpu") == "all"), {})
                        mem = row.get("memory", {})
                        net = [item for item in row.get("network", {}).get("net-dev", [])
                               if item.get("iface") != "lo"]
                        idle = all_cpu.get("idle")
                        result[label].append({
                            "at": at.isoformat(),
                            "cpu_pct": round(100 - idle - all_cpu.get("iowait", 0), 2) if idle is not None else None,
                            "mem_pct": mem.get("memused-percent"),
                            "rx_kib_s": round(sum(item.get("rxkB", 0) for item in net), 2) if net else None,
                            "tx_kib_s": round(sum(item.get("txkB", 0) for item in net), 2) if net else None,
                        })
    return {"available": bool(result["before"] and result["after"]), "windows": result}

start_at = dt.datetime.now(UTC)
start_connections = connections()
samples = [sample()]
for _ in range(6):
    time.sleep(5)
    samples.append(sample())
end_connections = connections()
end_at = dt.datetime.now(UTC)
first, end = samples[0], samples[-1]
elapsed = end["at"] - first["at"]
n_cpu = os.cpu_count() or 1
same_service = bool(first["service_pid"]) and first["service_pid"] == end["service_pid"]
service_cpu_ns = rate(first["service_cpu"], end["service_cpu"], elapsed) if same_service else None
used = [x["mem_total"] - x["mem_available"] for x in samples]
net = {direction: round(sum(max(0, end["net"][key][idx] - values[idx])
                            for key, values in first["net"].items() if key in end["net"]) / elapsed / 1024, 2)
       for idx, direction in enumerate(("rx_kib_s", "tx_kib_s"))}
cpu_points = [percent(previous, current) for previous, current in zip(samples, samples[1:])]
svc_rates = {direction: rate(first[key], end[key], elapsed)
             for key, direction in (("service_rx", "rx_bytes_sec"), ("service_tx", "tx_bytes_sec"))}
out = {
    "start": start_at.isoformat(), "end": end_at.isoformat(), "seconds": round(elapsed, 2),
    "host": {"cpus": n_cpu, "cpu_avg_pct": round(percent(first, end), 2),
             "cpu_peak_5s_pct": round(max(p for p in cpu_points if p is not None), 2),
             "memory_total_mib": round(end["mem_total"] / MIB, 2), "memory_avg_mib": avg_mib(used),
             "memory_peak_mib": peak_mib(used), "swap_peak_mib": peak_mib([x["swap_used"] for x in samples]),
             "net": net},
    "quote_service": {"process_stable": same_service,
                      "cpu_avg_pct_1core": round(service_cpu_ns / 1e7, 3) if service_cpu_ns is not None else None,
                      "cgroup_memory_avg_mib": avg_mib([x["service_mem"] for x in samples]),
                      "rss_avg_mib": avg_mib([x["service_rss"] for x in samples]),
                      "rss_peak_mib": peak_mib([x["service_rss"] for x in samples]),
                      "port443_established_start_end": [start_connections, end_connections],
                      "network_accounting": svc_rates if same_service else {}},
    "historical": historical(),
}
print("QUOTE_RESOURCE_MEASUREMENT=" + json.dumps(out, separators=(",", ":")), flush=True)
