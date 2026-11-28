"""Read-only: server load, memory, disk and the busiest processes."""
import os, shutil, subprocess
print("LOAD " + open("/proc/loadavg").read().strip() + " cpus=%d" % os.cpu_count(), flush=True)
mem = dict(l.split(":", 1) for l in open("/proc/meminfo"))
print("MEM total=%s available=%s" % (mem["MemTotal"].strip(), mem["MemAvailable"].strip()), flush=True)
d = shutil.disk_usage("/")
print("DISK used=%.1fGB free=%.1fGB" % (d.used / 1e9, d.free / 1e9), flush=True)
out = subprocess.run(["ps", "-eo", "pcpu,pmem,rss,etime,args", "--sort=-pcpu"], text=True, capture_output=True).stdout
for line in out.splitlines()[:9]:
    print("PS " + line[:150], flush=True)
