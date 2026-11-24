import os,stat,subprocess,json
p="/etc/gaemigtp/kiwoom.env"
try:
 st=os.stat(p)
 print("ENVFILE",{"readable":os.access(p,os.R_OK),"mode":oct(stat.S_IMODE(st.st_mode)),"uid":st.st_uid,"gid":st.st_gid},flush=True)
except Exception as e: print("ENVFILE_ERROR",type(e).__name__,flush=True)
cmd="set -a; . /etc/gaemigtp/kiwoom.env >/dev/null 2>&1; set +a; PYTHONPATH=/opt/gaemigtp-news/app python3 - <<'PY'\nimport os,json,time\nfrom backend.providers.kiwoom_us_industries import ETF_TICKERS,fetch_us_etf_exchanges,fetch_us_etf_marketcap\nprint('CRED_KEYS_PRESENT',bool(os.getenv('KIWOOM_APP_KEY')),bool(os.getenv('KIWOOM_APP_SECRET')),flush=True)\ntry:\n t=time.monotonic(); x=fetch_us_etf_marketcap(limit=100); rows=x.get('items',[]) if isinstance(x,dict) else []; print('MARKETCAP',len(rows),sorted({str(r.get('symbol','')).upper() for r in rows}&ETF_TICKERS),flush=True)\nexcept Exception as e: print('MARKETCAP_ERROR',type(e).__name__,repr(e),flush=True)\ntry:\n t=time.monotonic(); x=fetch_us_etf_exchanges(); print('EXCHANGES',json.dumps(x,sort_keys=True),'COUNT',len(x),'SECONDS',round(time.monotonic()-t,2),flush=True)\nexcept Exception as e: print('EXCHANGES_ERROR',type(e).__name__,repr(e),flush=True)\nPY";
r=subprocess.run(["bash","-lc",cmd],capture_output=True,text=True,timeout=75)
print("RESULT_RC",r.returncode,flush=True)
print("RESULT_OUT",r.stdout[-9000:],flush=True)
print("RESULT_ERR",r.stderr[-2000:],flush=True)
