"""Check persistent cursor continuity without fetching news or changing cursor."""
import json
from pathlib import Path
p=Path("/var/lib/gaemigtp-news/rotation.json")
s=json.loads(p.read_text())
proof=Path("/var/lib/gaemigtp-news/restart-proof.json")
now={"cycle":s.get("cycle_number"),"index":s.get("next_index"),"pending":s.get("pending")}
if proof.exists():
 old=json.loads(proof.read_text())
 assert now["cycle"]>old["cycle"] or (now["cycle"]==old["cycle"] and now["index"]>=old["index"]), "rotation_regressed"
 print("ROTATION_CONTINUITY_PASS",json.dumps({"before":old,"after":now}),flush=True)
else:
 proof.write_text(json.dumps(now))
 print("ROTATION_BASELINE_SAVED",json.dumps(now),flush=True)
