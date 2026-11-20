import subprocess
p=subprocess.run(["sudo","-n","cat","/usr/local/sbin/gaemi-do-gateway"],capture_output=True,text=True,check=True)
lines=p.stdout.splitlines()
needles=("deploy)","deploy ","systemctl restart","systemctl try-restart","restart ","install -m","cp ")
hits=set()
for i,line in enumerate(lines):
    if any(n in line for n in needles):
        for j in range(max(0,i-5),min(len(lines),i+12)):
            hits.add(j)
for i in sorted(hits):
    print(f"{i+1}: {lines[i]}")
