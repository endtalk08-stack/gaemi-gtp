"""Prepare (not install) minimal, checked DO news-worker rotation patch.

Usage: python ops/prepare_do_top20_news_patch.py LIVE_WORKER LIVE_NEWS_RESULT OUT_DIR
Inputs come from read-only SCP of the *actual running server*, never an
assumed copy from main. Output is staged only under the deploy user's HOME.
"""
from __future__ import annotations
import hashlib
import pathlib
import re
import sys

EXPECTED_WORKER = "d274422a687d89af56868a956dc77317945220cebac13b620f20c78f5ef73967"
EXPECTED_NEWS = "0f79aeb99a5931f22273ce4250c8cc3c9eca08734811add49c5ffd7a798f7a58"


def replace_once(content: str, before: str, after: str, label: str) -> str:
    if content.count(before) != 1:
        raise ValueError(f"unrecognized server code at {label}: {content.count(before)} matches")
    return content.replace(before, after, 1)


def replace_function(content: str, first: str, second: str, replacement: str) -> str:
    pattern = r"(?ms)^def " + re.escape(first) + r"\(.*?(?=^def " + re.escape(second) + r"\()"
    result, n = re.subn(pattern, lambda _m: replacement + "\n\n", content)
    if n != 1:
        raise ValueError("unexpected function layout: " + first)
    return result


STATE_HELPERS = '''
# Rotation progress is local metadata (not article data and not Neon).
# /var/tmp survives ordinary service restarts; each write is atomic and mode 0600.
ROTATION_STATE_PATH = "/var/tmp/gaemigtp-news-top20-rotation.json"

def _read_rotation_state():
    from pathlib import Path
    path = Path(ROTATION_STATE_PATH)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("invalid_rotating_state_file")
    return value

def _write_rotation_state(state):
    import tempfile
    from pathlib import Path
    path = Path(ROTATION_STATE_PATH)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(path.parent),
            prefix=".gaemigtp-rotation-", delete=False,
        ) as handle:
            name = handle.name
            os.fchmod(handle.fileno(), 0o600)
            json.dump(state, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)

'''

NEW_SELECTOR = '''def next_ranked_stock(state):
    from backend.services.us_top20_rotation import plan_tick, RankingUnavailable
    # Fetch a new top-20 ranking only when a new 20-stock cycle starts.
    # If ranking lookup fails, reuse the last complete frozen cycle (not a partial one).
    ranked_rows = []
    if not state.get("cycle") or state.get("next_index", 20) >= 20:
        market, query, path = RANKING_ENDPOINTS[0]
        try:
            ranked_rows = read_ranked_stocks(market, query, path)
            print(f"[news-worker] ranking market={market} matches={len(ranked_rows)}", flush=True)
        except Exception as exc:
            print(f"[news-worker] ranking_error={type(exc).__name__}", flush=True)
    try:
        item, new_state = plan_tick(state, ranked_rows)
    except RankingUnavailable:
        print("[news-worker] top20 ranking unavailable; no stock skipped", flush=True)
        return None
    state.clear()
    state.update(new_state)
    # Save pending cursor BEFORE doing provider/API work.
    _write_rotation_state(state)
    return "미국", item["name"], item["symbol"]'''

NEW_RUN_ONCE_START = '''def run_once(state):
    target = next_ranked_stock(state)
    if target is not None:
        from backend.services.us_top20_rotation import finish_tick
        market, stock_name, symbol = target
        ok = False
        try:
            result = process_stock(market, stock_name)
            ok = True
            print(f"[news-worker] market={market} stock={stock_name} {result}", flush=True)
        except Exception as exc:
            print(f"[news-worker] market={market} stock={stock_name} error={type(exc).__name__}", flush=True)
        finally:
            new_state = finish_tick(state, symbol, ok=ok)
            _write_rotation_state(new_state)
            state.clear()
            state.update(new_state)
'''


def patch_worker(source):
    source = replace_once(
        source,
        'RANKING_REFRESH_SECONDS = 300  # Refresh the trading-value TOP20 feed\nRANKED_STOCK_COOLDOWN_SECONDS = 1800\n',
        '# One ticker each worker tick; current 20-symbol ranking frozen for full round.\n',
        "obsolete cooldown",
    )
    source = replace_once(
        source, 'and (market, name) not in selected):',
        'and not any(x["symbol"] == symbol or x["display_name"] == name for x in selected)):',
        "symbol identity check",
    )
    source = replace_once(
        source, 'selected.append((market, name))\n    return selected',
        'selected.append({"rank": len(selected) + 1, "symbol": symbol, "display_name": name})\n'
        '    if len(selected) != 20:\n'
        '        raise ValueError("incomplete_us_top20_ranking")\n'
        '    return selected',
        "20 ranked tickers",
    )
    source = replace_function(source, "next_ranked_stock", "process_stock", NEW_SELECTOR)
    source = replace_once(
        source,
        'def run_once(state):\n    target = next_ranked_stock(state)\n    if target is not None:\n        market, stock_name = target\n        try:\n            result = process_stock(market, stock_name)\n            print(f"[news-worker] market={market} stock={stock_name} {result}", flush=True)\n        except Exception as exc:\n            print(f"[news-worker] market={market} stock={stock_name} error={type(exc).__name__}", flush=True)\n',
        NEW_RUN_ONCE_START, "stock round progress",
    )
    source = replace_once(
        source, 'state = {"last_ranking_fetch": -1e10, "ranking_index": 0,\n'
                '             "ranked": [], "last_processed": {}, "cursor": 0}',
        'state = _read_rotation_state()', "startup resume",
    )
    source = replace_once(source, 'def read_ranked_stocks(market, query, path):',
                          STATE_HELPERS + 'def read_ranked_stocks(market, query, path):',
                          "local rotation metadata state")
    return source


def patch_news(source):
    source = replace_once(source,
        "        candidate_news = rank_candidates(paired_news_items)\n"
        "        candidate_news.extend(rank_candidates(older_news))",
        "        candidate_news = rank_candidates(paired_news_items)\n"
        '        is_us_24h = market in ("미국", "us", "US")\n'
        "        if not is_us_24h:\n"
        "            candidate_news.extend(rank_candidates(older_news))\n"
        "        issue_count_limit = max(1, len(candidate_news)) if is_us_24h else storyboard_limit",
        "US selection without 3-cap")
    for old, new, tag in (
        ("                accepted_articles, limit=storyboard_limit,",
         "                accepted_articles, limit=issue_count_limit,", "final article selection"),
        ("            if len(storyboard_news_items) >= storyboard_limit:",
         "            if len(storyboard_news_items) >= issue_count_limit:", "batch continuation"),
        ("            limit=storyboard_limit,\n            body_texts=verified_body_texts,",
         "            limit=issue_count_limit,\n            body_texts=verified_body_texts,",
         "verified issue briefs"),
    ):
        source = replace_once(source, old, new, tag)
    return source


def main():
    worker_path, news_path, output = map(pathlib.Path, sys.argv[1:4])
    originals = [
        (worker_path, EXPECTED_WORKER, patch_worker, "news_worker.py"),
        (news_path, EXPECTED_NEWS, patch_news, "news_result.py"),
    ]
    output.mkdir(parents=True, exist_ok=True)
    for source_file, expected, transform, filename in originals:
        raw = source_file.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise RuntimeError("server code changed; refusing to overwrite " + filename)
        transformed = transform(raw.decode("utf-8"))
        compile(transformed, filename, "exec")
        destination = output / filename
        destination.write_text(transformed, encoding="utf-8")
        print("PATCH_PREPARED", filename, len(raw), len(transformed.encode("utf-8")))


if __name__ == "__main__":
    main()
