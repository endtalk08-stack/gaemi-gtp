"""Read-only verification of exact pre-change restored DigitalOcean files."""
from pathlib import Path
import hashlib
import subprocess

base = Path("/opt/gaemigtp-news/app/backend")
expected = {
    "services/news_result.py": "294aa00b46bbcb64602f9d05f619af1911fe83018d0cd1a81d2d8da9efb36d0d",
    "services/news_processed_store.py": "878c658c84072dd9046464ae6b8bf67174a69f6da5ad84fb7b2cdded72163618",
    "services/news_feed.py": "a4544237a20b45cc02ddf9a320741acd6a5c2c04c6a9db20e503442a5834c7a0",
    "services/us_top20_rotation.py": "53b7082d2bd009867377b70c813b7bc1f1f773939a7d3c3f474859f6f6a65b65",
    "news_worker.py": "b1706dd0ab3200d7c3f3fbce4c086ef2266cf66e834a29aa936e2f640b85c2cd",
}
for rel, expected_sha in expected.items():
    path = base / rel
    if not path.is_file() or path.is_symlink():
        raise AssertionError("MISSING_FILE_" + rel)
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha:
        raise AssertionError("SHA_MISMATCH_" + rel + ":" + actual)
    if rel.endswith("news_result.py") or rel.endswith("news_processed_store.py"):
        compile(data, rel, "exec")
    print("ROLLBACK_SHA_OK", rel, actual, flush=True)

result = (base / "services/news_result.py").read_text()
store = (base / "services/news_processed_store.py").read_text()
assert '"_code_source_revision": 13' in result
assert 'payload.get("_code_source_revision") != 13' in store
assert 'if market not in ("미국", "US", "us") and not central_material_brief_supported(excerpt):' in result
assert "attach_verified_source_citations(" in result
print("ROLLBACK_PRECHANGE_CODE_OK", flush=True)
check = subprocess.run(["systemctl", "is-active", "gaemigtp-news.service"], capture_output=True, text=True)
if check.returncode != 0 or check.stdout.strip() != "active":
    raise AssertionError("SERVICE_NOT_ACTIVE")
print("ROLLBACK_SERVICE_ACTIVE", flush=True)
