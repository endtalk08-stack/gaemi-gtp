"""Idempotent source patch: retain previously fetched ranking-feed candidates.
The existing DigitalOcean worker must continue to fetch only one ranking
endpoint and process at most one extra stock per worker cycle.
"""
from pathlib import Path
import ast
import sys

def patch_content(source):
    marker='state.setdefault("ranked_by_feed", {})'
    if marker in source:
        return source, False
    old='''            state["ranked"] = current
            print(f"[news-worker] ranking market={market} matches={len(current)}", flush=True)'''
    new='''            # Do not lose other top-20 feeds every time the endpoint rotates.
            # Keep the latest bounded candidates for all four feed types.
            feeds = state.setdefault("ranked_by_feed", {})
            feeds[(market, path)] = current
            state["ranked"] = list(dict.fromkeys(
                pair for rows in feeds.values() for pair in rows
            ))
            print(f"[news-worker] ranking market={market} matches={len(current)}", flush=True)'''
    old_fail='''            state["ranked"] = []  # Never keep targeting an obsolete TOP20 feed.
            print(f"[news-worker] ranking_error={type(exc).__name__}", flush=True)'''
    new_fail='''            # Remove only the failed feed, preserving other freshly read feeds.
            feeds = state.setdefault("ranked_by_feed", {})
            feeds[(market, path)] = []
            state["ranked"] = list(dict.fromkeys(
                pair for rows in feeds.values() for pair in rows
            ))
            print(f"[news-worker] ranking_error={type(exc).__name__}", flush=True)'''
    if source.count(old)!=1 or source.count(old_fail)!=1:
        raise ValueError("Ranking scheduler baseline changed; refuse to patch")
    updated=source.replace(old,new).replace(old_fail,new_fail)
    ast.parse(updated)
    return updated, True

if __name__ == "__main__":
    p=Path(sys.argv[1])
    previous=p.read_text()
    updated,changed=patch_content(previous)
    if changed:
        backup=p.with_name(p.name+".pre_coverage_20261018.bak")
        if not backup.exists():
            backup.write_text(previous)
        p.write_text(updated)
    print("RANK_QUEUE_PATCH", "APPLIED" if changed else "ALREADY_APPLIED")
