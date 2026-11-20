from pathlib import Path
p=Path("/usr/local/sbin/gaemi-do-gateway")
s=p.read_text()
lines=s.splitlines()
needles=("deploy)","deploy ","def deploy","case ","systemctl restart","systemctl try-restart","restart ")
hits=set()
for i,line in enumerate(lines):
    if any(n in line for n in needles):
        for j in range(max(0,i-5),min(len(lines),i+10)):
            hits.add(j)
for i in sorted(hits):
    print(f"{i+1}: {lines[i]}")
