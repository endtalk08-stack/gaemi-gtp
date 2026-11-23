from pathlib import Path
import hashlib
import subprocess
root = Path('/opt/gaemigtp-news/app')
for rel in ('backend/kiwoom_us_live_prices.py', 'backend/kiwoom_us_top20_api.py', 'backend/providers/kiwoom_us_quotes.py', 'backend/us_quote_change.py', 'frontend/shell/left-market-sidebar/market-sidebar.js'):
    path = root / rel
    if path.is_file() and not path.is_symlink():
        import subprocess
        print(rel, subprocess.check_output(['git', 'hash-object', str(path)], text=True).strip(), flush=True)
    else:
        print(rel, 'ABSENT', flush=True)
