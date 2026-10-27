import pathlib, subprocess
root=pathlib.Path("/opt/gaemigtp-news/app")
for p in [root/"backend/providers/kiwoom_us_quotes.py"]:
 print("FILE",str(p)); print(p.read_text())
for p in root.rglob("*.py"):
 if p.name=="kiwoom_us_quotes.py": continue
 s=p.read_text(errors="replace")
 if "us_daily_candles" in s or "fetch_us_daily_chart" in s:
  print("COLLECTOR_FILE",str(p)); print(s[:50000])
print(subprocess.run(["systemctl","list-timers","--all","--no-pager"],capture_output=True,text=True).stdout)
