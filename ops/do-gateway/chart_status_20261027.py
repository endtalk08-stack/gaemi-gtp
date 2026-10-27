import pathlib, subprocess, json
root=pathlib.Path("/opt/gaemigtp-news/app/backend")
for p in root.rglob("*.py"):
 s=p.read_text(errors="replace")
 if "us_daily_candles" in s and "INSERT INTO" in s:
  print("CANDLE_WRITER_MODULE="+str(p.relative_to(root)))
out=subprocess.run(["systemctl","list-timers","--all","--no-pager","gaemigtp-*"],capture_output=True,text=True).stdout
for line in out.splitlines():
 if any(k in line.lower() for k in ("daily","candle","chart","kiwoom")): print(line)
