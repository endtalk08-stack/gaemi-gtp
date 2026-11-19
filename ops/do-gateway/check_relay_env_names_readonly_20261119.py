"""Print only names of relay-related environment variables; never their values."""
import os
names=sorted(name for name in os.environ if "PRICE" in name.upper() or "RELAY" in name.upper())
print("NEWS_WORKER_RELAY_ENV_NAMES="+",".join(names),flush=True)
