"""Read-only post-deploy verification for exactly two approved US CODE files."""
from pathlib import Path
import hashlib
import subprocess

base = Path("/opt/gaemigtp-news/app/backend")
expected = {
    "services/news_result.py": "ce107a7c56210e46664186c7336a1f3fbef41fe2c54baa2b2d5ab989e87e421d",
    "services/news_processed_store.py": "d6b6c2ff4516779c4183f253c445c48fd5eb81bef6447a1ea2819249403e78f9",
    "services/news_feed.py": "a4544237a20b45cc02ddf9a320741acd6a5c2c04c6a9db20e503442a5834c7a0",
    "services/us_top20_rotation.py": "53b7082d2bd009867377b70c813b7bc1f1f773939a7d3c3f474859f6f6a65b65",
    "news_worker.py": "b1706dd0ab3200d7c3f3fbce4c086ef2266cf66e834a29aa936e2f640b85c2cd",
}
for rel, expected_sha in expected.items():
    path = base/rel
    if not path.is_file() or path.is_symlink():
        raise AssertionError("FILE_MISSING_"+rel)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha:
        raise AssertionError("FILE_HASH_MISMATCH_"+rel+": "+actual)
    print("PRESERVED_OR_RESTORED_FILE", rel, actual, flush=True)
result = (base/"services/news_result.py").read_text()
store = (base/"services/news_processed_store.py").read_text()
compile(result,"news_result.py","exec")
compile(store,"news_processed_store.py","exec")
assert "select_stock_news_for_analysis(raw_news_list, stock_name, limit)" in result
assert 'if not central_material_brief_supported(excerpt):' in result
assert 'if market not in ("미국", "US", "us") and not central_material_brief_supported(excerpt):' not in result
assert 'limit = max(12, storyboard_limit * 3)' in result
assert 'issue_count_limit = storyboard_limit' in result
assert "attach_verified_source_citations(" in result
assert 'brief["headline"] = re.sub(r"\\s*이슈\\s*$"' not in result
assert '"_code_source_revision": 14' in result
assert 'payload.get("_code_source_revision") != 14' in store
assert 'payload.get("_kr_selection_revision") != 1' in store
assert "def _prefer_same_day_ai(" in store
assert "def _same_stock_issue_briefs(" in store
print("US_KR_RESULT_AND_CACHE_VALIDATED", flush=True)
check = subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True)
assert check.returncode == 0 and check.stdout.strip() == "active", "NEWS_SERVICE_NOT_ACTIVE"
print("WORKER_SERVICE_ACTIVE", flush=True)
