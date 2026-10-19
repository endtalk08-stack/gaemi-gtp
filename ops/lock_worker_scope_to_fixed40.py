"""Guard existing DigitalOcean news worker against out-of-40 processing.

No provider calls, no AI invocation, no scheduling, no automatic restart.
Use --check to inspect patch compatibility; --install only after scoped tests.
"""
import argparse
import ast
import hashlib
import os
from pathlib import Path

NEWS_WORKER = Path("/opt/gaemigtp-news/app/backend/news_worker.py")
IMPORT = "from backend.services.stock_scope import resolve_stock"
BEFORE_PROCESS = "def process_stock(market, stock_name):\n"
AFTER_PROCESS = (
    "def process_stock(market, stock_name):\n"
    "    # Only user-selected KR20 + US20 may trigger news or paid AI.\n"
    "    if resolve_stock(stock_name, market=market) is None:\n"
    "        return 'skipped_outside_fixed40'\n"
)
BEFORE_RANKED = (
    "    targets = list(stocks)\n"
    "    if state is not None:\n"
    "        extra = next_ranked_stock(set(stocks), state)\n"
    "        if extra is not None:\n"
    "            targets.append(extra)\n"
)
AFTER_RANKED = (
    "    # Never insert a ranking stock into the news/AI collection queue.\n"
    "    # The separate market rankings still operate completely unchanged.\n"
    "    targets = [(market, name) for market, name in stocks\n"
    "               if resolve_stock(name, market=market) is not None]\n"
)


def patch_source(source):
    if IMPORT in source and AFTER_RANKED in source and AFTER_PROCESS in source:
        return source
    if IMPORT in source or AFTER_RANKED in source or AFTER_PROCESS in source:
        raise ValueError("worker_is_partially_patched")
    if source.count(BEFORE_PROCESS) != 1 or source.count(BEFORE_RANKED) != 1:
        raise ValueError("unexpected_worker_source_no_write")
    # No price/feed/AI function is invoked at patch time.
    amended = IMPORT + "\n" + source
    amended = amended.replace(BEFORE_PROCESS, AFTER_PROCESS, 1)
    amended = amended.replace(BEFORE_RANKED, AFTER_RANKED, 1)
    compile(amended, str(NEWS_WORKER), "exec")
    tree = ast.parse(amended)
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "process_stock" in defs and "run_once" in defs
    assert "next_ranked_stock(" not in ast.get_source_segment(amended, defs["run_once"])
    return amended


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.check == args.install:
        parser.error("choose exactly one --check or --install")
    original = NEWS_WORKER.read_text()
    changed = patch_source(original)
    print("NEWS_WORKER_SCOPE_CHECK=PASS")
    print("CHANGE_NEEDED=" + str(changed != original).lower())
    if not args.install or changed == original:
        return
    assert NEWS_WORKER.is_file() and os.access(NEWS_WORKER, os.W_OK)
    backup = NEWS_WORKER.with_name("news_worker.py.fixed40-before")
    if backup.exists():
        assert backup.read_text() == original, "backup_is_not_expected_source"
    else:
        backup.write_text(original)
        backup.chmod(0o600)
    tmp = NEWS_WORKER.with_name("news_worker.py.fixed40-new")
    tmp.write_text(changed)
    compile(tmp.read_text(), str(tmp), "exec")
    tmp.chmod(0o644)
    os.replace(tmp, NEWS_WORKER)
    print("NEWS_WORKER_PATCHED_ON_DISK=YES")
    print("NEWS_WORKER_RESTARTED=NO")


if __name__ == "__main__":
    main()
